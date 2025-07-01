"""
Intelligent worldbuilding selection for scene integration.

This module provides semantic, LLM-based selection of relevant worldbuilding
elements for each scene, avoiding brittle keyword matching.
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from pydantic import BaseModel, Field

from storyteller_lib.core.config import llm
from storyteller_lib.core.logger import get_logger
from storyteller_lib.persistence.database import get_db_manager

logger = get_logger(__name__)


class SceneWorldbuildingNeeds(BaseModel):
    """Analysis of what worldbuilding elements would enhance a scene."""
    
    location_details: List[str] = Field(
        default_factory=list,
        description="Specific location/geography information needed"
    )
    cultural_context: List[str] = Field(
        default_factory=list,
        description="Cultural norms, customs, or social dynamics relevant to the scene"
    )
    historical_references: List[str] = Field(
        default_factory=list,
        description="Historical events or context that would inform the scene"
    )
    economic_factors: List[str] = Field(
        default_factory=list,
        description="Economic elements visible or relevant to the action"
    )
    political_elements: List[str] = Field(
        default_factory=list,
        description="Power structures, laws, or political tensions affecting the scene"
    )
    religious_aspects: List[str] = Field(
        default_factory=list,
        description="Religious practices, beliefs, or institutions relevant"
    )
    technology_magic_usage: List[str] = Field(
        default_factory=list,
        description="Technology or magic systems that might appear or influence"
    )
    daily_life_details: List[str] = Field(
        default_factory=list,
        description="Everyday life elements that add authenticity"
    )


class WorldbuildingSelection(BaseModel):
    """A selected worldbuilding element with relevance explanation."""
    
    category: str = Field(description="Worldbuilding category")
    element_key: str = Field(description="Specific element within category")
    relevance_reason: str = Field(description="Why this element is relevant to the scene")
    suggested_usage: str = Field(description="How to incorporate this element")
    priority: str = Field(description="Priority level: essential, important, or atmospheric")


class WorldbuildingSelections(BaseModel):
    """Collection of selected worldbuilding elements for a scene."""
    
    selections: List[WorldbuildingSelection] = Field(
        description="Selected worldbuilding elements ordered by relevance"
    )


class RelevantWorldbuildingSnippet(BaseModel):
    """Extracted relevant portion of worldbuilding content."""
    
    category: str
    element_key: str
    full_content: str
    relevant_excerpt: str = Field(
        description="The specific portion most relevant to this scene"
    )
    integration_note: str = Field(
        description="Brief note on how to integrate this into the scene"
    )


@dataclass
class SceneContext:
    """Structured scene context for worldbuilding selection."""
    description: str
    scene_type: str
    location: str
    characters: List[str]
    plot_threads: List[str]
    dramatic_purpose: str
    chapter_themes: List[str]
    previous_scene_summary: Optional[str] = None


class WorldbuildingSelector:
    """Intelligent selector for scene-relevant worldbuilding elements."""
    
    def __init__(self):
        self.db_manager = get_db_manager()
        self._worldbuilding_cache = None
        
    def get_all_worldbuilding(self) -> Dict[str, Dict[str, str]]:
        """Retrieve all worldbuilding from database."""
        if self._worldbuilding_cache is not None:
            return self._worldbuilding_cache
            
        worldbuilding = {}
        with self.db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT category, element_key, element_value
                FROM world_elements
                ORDER BY category, element_key
            """)
            
            for row in cursor.fetchall():
                category = row['category']
                if category not in worldbuilding:
                    worldbuilding[category] = {}
                worldbuilding[category][row['element_key']] = row['element_value']
        
        self._worldbuilding_cache = worldbuilding
        logger.info(f"Loaded worldbuilding from database: {len(worldbuilding)} categories, "
                   f"{sum(len(v) for v in worldbuilding.values())} total elements")
        return worldbuilding
    
    def analyze_scene_needs(self, scene_context: SceneContext) -> SceneWorldbuildingNeeds:
        """Analyze what worldbuilding elements would enhance the scene."""
        logger.info(f"Analyzing worldbuilding needs for scene: {scene_context.description[:100]}...")
        
        prompt = f"""
Analyze what worldbuilding context would enhance this scene:

Scene Description: {scene_context.description}
Scene Type: {scene_context.scene_type}
Location: {scene_context.location}
Characters Involved: {', '.join(scene_context.characters)}
Plot Threads: {', '.join(scene_context.plot_threads)}
Dramatic Purpose: {scene_context.dramatic_purpose}
Chapter Themes: {', '.join(scene_context.chapter_themes)}

Based on this scene, identify what specific worldbuilding information would be most valuable:

1. What location/geography details would help visualize the setting?
2. What cultural norms or customs might influence character behavior?
3. What historical context might add depth or irony?
4. What economic factors might be visible or influence actions?
5. What political elements might create tension or obstacles?
6. What religious aspects might affect the scene?
7. What technology/magic might be used or referenced?
8. What daily life details would add authenticity?

Be specific about what information would actually enhance THIS PARTICULAR SCENE.
Don't list generic needs - focus on what's relevant to the actual events and characters.
"""
        
        structured_llm = llm.with_structured_output(SceneWorldbuildingNeeds)
        needs = structured_llm.invoke(prompt)
        
        logger.debug(f"Identified needs: {needs.model_dump()}")
        return needs
    
    def select_relevant_elements(
        self, 
        scene_context: SceneContext,
        scene_needs: SceneWorldbuildingNeeds,
        max_elements: int = 7
    ) -> WorldbuildingSelections:
        """Select the most relevant worldbuilding elements for the scene."""
        worldbuilding = self.get_all_worldbuilding()
        
        # Create a summary of available worldbuilding
        wb_summary = self._create_worldbuilding_summary(worldbuilding)
        
        prompt = f"""
Given this scene context and identified needs, select the most relevant worldbuilding elements:

SCENE CONTEXT:
{scene_context.description}
Location: {scene_context.location}
Type: {scene_context.scene_type}
Purpose: {scene_context.dramatic_purpose}

IDENTIFIED NEEDS:
- Location details: {', '.join(scene_needs.location_details) or 'None identified'}
- Cultural context: {', '.join(scene_needs.cultural_context) or 'None identified'}
- Historical references: {', '.join(scene_needs.historical_references) or 'None identified'}
- Economic factors: {', '.join(scene_needs.economic_factors) or 'None identified'}
- Political elements: {', '.join(scene_needs.political_elements) or 'None identified'}
- Religious aspects: {', '.join(scene_needs.religious_aspects) or 'None identified'}
- Technology/Magic: {', '.join(scene_needs.technology_magic_usage) or 'None identified'}
- Daily life: {', '.join(scene_needs.daily_life_details) or 'None identified'}

AVAILABLE WORLDBUILDING:
{wb_summary}

Select up to {max_elements} worldbuilding elements that would best serve this scene.
For each selection, explain:
1. Why it's relevant to this specific scene
2. How it should be incorporated
3. Whether it's essential, important, or just atmospheric

Prioritize elements that:
- Directly support the scene's action or dialogue
- Provide necessary context for character motivations
- Enhance the atmosphere without overwhelming
- Add authentic detail that serves the story

Avoid elements that:
- Are tangentially related but not actually useful
- Would distract from the scene's focus
- Have already been extensively covered
"""
        
        structured_llm = llm.with_structured_output(WorldbuildingSelections)
        selections = structured_llm.invoke(prompt)
        
        logger.info(f"Selected {len(selections.selections)} worldbuilding elements")
        return selections
    
    def extract_relevant_snippets(
        self,
        selections: WorldbuildingSelections,
        scene_context: SceneContext
    ) -> List[RelevantWorldbuildingSnippet]:
        """Extract only the relevant portions of selected worldbuilding."""
        worldbuilding = self.get_all_worldbuilding()
        snippets = []
        
        for selection in selections.selections:
            full_content = worldbuilding.get(selection.category, {}).get(selection.element_key, "")
            
            if not full_content:
                logger.warning(f"No content found for {selection.category}.{selection.element_key}")
                continue
            
            prompt = f"""
Extract the most relevant portion of this worldbuilding content for the scene:

SCENE CONTEXT: {scene_context.description}
RELEVANCE REASON: {selection.relevance_reason}
SUGGESTED USAGE: {selection.suggested_usage}

FULL WORLDBUILDING CONTENT:
{full_content}

Extract 1-3 sentences that are most relevant to this specific scene.
Also provide a brief note on how to naturally integrate this information.

Focus on:
- Information that directly supports the scene's action
- Details that enhance understanding without exposition
- Elements that can be shown through action/dialogue rather than told
"""
            
            class SnippetExtraction(BaseModel):
                relevant_excerpt: str = Field(description="Most relevant 1-3 sentences")
                integration_note: str = Field(description="How to naturally include this")
            
            structured_llm = llm.with_structured_output(SnippetExtraction)
            extraction = structured_llm.invoke(prompt)
            
            snippets.append(RelevantWorldbuildingSnippet(
                category=selection.category,
                element_key=selection.element_key,
                full_content=full_content,
                relevant_excerpt=extraction.relevant_excerpt,
                integration_note=extraction.integration_note
            ))
        
        return snippets
    
    def _create_worldbuilding_summary(self, worldbuilding: Dict[str, Dict[str, str]]) -> str:
        """Create a concise summary of available worldbuilding elements."""
        summary_lines = []
        
        for category, elements in worldbuilding.items():
            if elements:
                element_list = []
                for key, content in elements.items():
                    # First 100 chars of content as preview
                    preview = content[:100].replace('\n', ' ') + "..." if len(content) > 100 else content
                    element_list.append(f"  - {key}: {preview}")
                
                summary_lines.append(f"{category.upper()}:")
                summary_lines.extend(element_list[:5])  # Limit to 5 per category
                summary_lines.append("")
        
        return "\n".join(summary_lines)
    
    def select_worldbuilding_for_scene(
        self,
        chapter: int,
        scene: int,
        scene_description: str,
        scene_type: str,
        location: str,
        characters: List[str],
        plot_threads: List[str],
        dramatic_purpose: str,
        chapter_themes: List[str],
        previous_scene_summary: Optional[str] = None
    ) -> Dict[str, Any]:
        """Main entry point for selecting worldbuilding for a scene."""
        # Create scene context
        scene_context = SceneContext(
            description=scene_description,
            scene_type=scene_type,
            location=location,
            characters=characters,
            plot_threads=plot_threads,
            dramatic_purpose=dramatic_purpose,
            chapter_themes=chapter_themes,
            previous_scene_summary=previous_scene_summary
        )
        
        # Step 1: Analyze what the scene needs
        scene_needs = self.analyze_scene_needs(scene_context)
        
        # Step 2: Select relevant elements
        selections = self.select_relevant_elements(scene_context, scene_needs)
        
        # Step 3: Extract relevant snippets
        snippets = self.extract_relevant_snippets(selections, scene_context)
        
        # Format for use in scene generation
        formatted_elements = {}
        for snippet in snippets:
            if snippet.category not in formatted_elements:
                formatted_elements[snippet.category] = {}
            
            formatted_elements[snippet.category][snippet.element_key] = {
                'content': snippet.relevant_excerpt,
                'integration': snippet.integration_note,
                'full_content': snippet.full_content  # Keep full content for reference
            }
        
        return {
            'elements': formatted_elements,
            'needs_analysis': scene_needs.model_dump(),
            'selection_count': len(snippets)
        }


# Convenience function for use in existing code
def get_intelligent_world_context(
    scene_description: str,
    scene_type: str,
    location: str,
    characters: List[str],
    plot_threads: List[str],
    dramatic_purpose: str,
    chapter_themes: List[str],
    chapter: int,
    scene: int
) -> Dict[str, Any]:
    """Get intelligently selected worldbuilding context for a scene."""
    selector = WorldbuildingSelector()
    return selector.select_worldbuilding_for_scene(
        chapter=chapter,
        scene=scene,
        scene_description=scene_description,
        scene_type=scene_type,
        location=location,
        characters=characters,
        plot_threads=plot_threads,
        dramatic_purpose=dramatic_purpose,
        chapter_themes=chapter_themes
    )