"""
StoryCraft Agent - Graph construction and routing logic.
"""

from typing import Dict

from langgraph.graph import StateGraph, START, END

from storyteller_lib.models import StoryState
from storyteller_lib.config import store
from storyteller_lib.initialization import initialize_state, brainstorm_story_concepts
from storyteller_lib.outline import generate_story_outline, generate_characters, plan_chapters
from storyteller_lib.scenes import (
    brainstorm_scene_elements, 
    write_scene, 
    reflect_on_scene, 
    revise_scene_if_needed
)
from storyteller_lib.progression import (
    update_character_profiles, 
    review_continuity, 
    advance_to_next_scene_or_chapter, 
    compile_final_story
)
from storyteller_lib import track_progress

# Router function
@track_progress
def router(state: StoryState) -> Dict:
    """Route to the appropriate next node based on the current state."""
    next_node = ""
    
    # Safety check - if we're in an invalid state that might cause infinite recursion
    # terminate the execution by going to the compile_final_story node
    if "router_count" not in state:
        state["router_count"] = 0
    else:
        state["router_count"] += 1
        
    # If we've hit the router too many times, something is wrong - go to final node
    if state["router_count"] > 50:
        print("WARNING: Router has been called too many times. Terminating execution.")
        state["completed"] = True
        return {"next": "compile_final_story"}
    
    # Normal routing logic
    if "global_story" not in state or not state["global_story"]:
        if "creative_elements" not in state or not state.get("creative_elements"):
            next_node = "brainstorm_story_concepts"
        else:
            next_node = "generate_story_outline"
    
    elif "characters" not in state or not state["characters"]:
        next_node = "generate_characters"
    
    elif "chapters" not in state or not state["chapters"]:
        next_node = "plan_chapters"
    
    elif state.get("completed", False):
        next_node = "compile_final_story"
    
    else:
        # Get the current chapter and scene - add safety checks
        current_chapter = state.get("current_chapter", "")
        current_scene = state.get("current_scene", "")
        
        # Safety check - if current_chapter or current_scene are not set, go to plan_chapters
        if not current_chapter or not current_scene:
            print("WARNING: Current chapter or scene not set. Going back to planning.")
            return {"next": "plan_chapters"}
            
        # Safety check - make sure the chapter exists in the chapters dictionary
        if current_chapter not in state.get("chapters", {}):
            print(f"WARNING: Chapter {current_chapter} not found. Going back to planning.")
            return {"next": "plan_chapters"}
            
        chapter = state["chapters"][current_chapter]
        
        # Safety check - make sure the scene exists in the chapter
        if current_scene not in chapter.get("scenes", {}):
            print(f"WARNING: Scene {current_scene} not found in chapter {current_chapter}. Moving to next chapter.")
            return {"next": "advance_to_next_scene_or_chapter"}
        
        # Check if we need to brainstorm for the current scene
        scene_creative_key = f"scene_elements_ch{current_chapter}_sc{current_scene}"
        if "creative_elements" not in state or scene_creative_key not in state.get("creative_elements", {}):
            next_node = "brainstorm_scene_elements"
        
        # Check if the current scene has content
        elif not chapter["scenes"][current_scene].get("content"):
            next_node = "write_scene"
        
        # Check if the current scene has reflection notes
        elif not chapter["scenes"][current_scene].get("reflection_notes"):
            next_node = "reflect_on_scene"
        
        # Check if character profiles need updating (always do this after reflection)
        else:
            last_node = state.get("last_node", "")
            if last_node == "reflect_on_scene" or last_node == "revise_scene_if_needed":
                next_node = "update_character_profiles"
            
            # Check if we've updated characters and need to move to the next scene/chapter
            elif last_node == "update_character_profiles":
                # Time to check if we've completed a chapter
                all_scenes_complete = True
                for scene in chapter["scenes"].values():
                    if not scene.get("content") or not scene.get("reflection_notes"):
                        all_scenes_complete = False
                        break
                
                if all_scenes_complete and last_node != "review_continuity":
                    # If we've completed all scenes in the chapter, run a continuity review
                    next_node = "review_continuity"
                else:
                    # Otherwise, move to the next scene or chapter
                    next_node = "advance_to_next_scene_or_chapter"
            
            # If we just did a continuity review, now we can advance
            elif last_node == "review_continuity":
                next_node = "advance_to_next_scene_or_chapter"
            
            # Default to writing the next scene
            else:
                next_node = "write_scene"
    
    # Safety check - if we somehow haven't set a next node, default to compile_final_story
    if not next_node:
        print("WARNING: No next node determined. Terminating execution.")
        state["completed"] = True
        next_node = "compile_final_story"
        
    return {"next": next_node}

# Define routing logic
def route_to_next_node(state):
    """Extract the next node from the router output."""
    return state["next"]

# Build the graph
def build_story_graph():
    """
    Build and compile the story generation graph.
    """
    # Create a state graph
    graph_builder = StateGraph(StoryState)
    
    # Add nodes
    graph_builder.add_node("initialize_state", initialize_state)
    graph_builder.add_node("brainstorm_story_concepts", brainstorm_story_concepts)
    graph_builder.add_node("generate_story_outline", generate_story_outline)
    graph_builder.add_node("generate_characters", generate_characters)
    graph_builder.add_node("plan_chapters", plan_chapters)
    graph_builder.add_node("brainstorm_scene_elements", brainstorm_scene_elements)
    graph_builder.add_node("write_scene", write_scene)
    graph_builder.add_node("reflect_on_scene", reflect_on_scene)
    graph_builder.add_node("revise_scene_if_needed", revise_scene_if_needed)
    graph_builder.add_node("update_character_profiles", update_character_profiles)
    graph_builder.add_node("review_continuity", review_continuity)
    graph_builder.add_node("advance_to_next_scene_or_chapter", advance_to_next_scene_or_chapter)
    graph_builder.add_node("compile_final_story", compile_final_story)
    graph_builder.add_node("router", router)
    
    # Add edges
    graph_builder.add_edge(START, "initialize_state")
    graph_builder.add_edge("initialize_state", "router")
    graph_builder.add_edge("brainstorm_story_concepts", "router")
    graph_builder.add_edge("generate_story_outline", "router")
    graph_builder.add_edge("generate_characters", "router")
    graph_builder.add_edge("plan_chapters", "router")
    graph_builder.add_edge("brainstorm_scene_elements", "router")
    graph_builder.add_edge("write_scene", "router")
    graph_builder.add_edge("reflect_on_scene", "revise_scene_if_needed")
    graph_builder.add_edge("revise_scene_if_needed", "router")
    graph_builder.add_edge("update_character_profiles", "router")
    graph_builder.add_edge("review_continuity", "router")
    graph_builder.add_edge("advance_to_next_scene_or_chapter", "router")
    graph_builder.add_edge("compile_final_story", END)
    
    # Add conditional edge for routing based on the 'next' field in router output
    graph_builder.add_conditional_edges(
        "router",
        route_to_next_node,
        {
            "brainstorm_story_concepts": "brainstorm_story_concepts",
            "generate_story_outline": "generate_story_outline",
            "generate_characters": "generate_characters",
            "plan_chapters": "plan_chapters",
            "brainstorm_scene_elements": "brainstorm_scene_elements",
            "write_scene": "write_scene",
            "reflect_on_scene": "reflect_on_scene",
            "revise_scene_if_needed": "revise_scene_if_needed",
            "update_character_profiles": "update_character_profiles",
            "review_continuity": "review_continuity",
            "advance_to_next_scene_or_chapter": "advance_to_next_scene_or_chapter",
            "compile_final_story": "compile_final_story"
        }
    )
    
    # Compile the graph normally - we'll handle progress tracking in node functions
    graph = graph_builder.compile()
    
    # Return the compiled graph
    return graph