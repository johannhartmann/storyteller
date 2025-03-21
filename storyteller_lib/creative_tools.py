"""
StoryCraft Agent - Creative tools and utilities.
"""

from typing import Dict, List
import json

from storyteller_lib.config import llm, manage_memory_tool, MEMORY_NAMESPACE
from langchain_core.messages import HumanMessage

def creative_brainstorm(
    topic: str, 
    genre: str, 
    tone: str, 
    context: str, 
    author: str = "", 
    author_style_guidance: str = "",
    num_ideas: int = 5,
    evaluation_criteria: List[str] = None
) -> Dict:
    """
    Generate and evaluate multiple creative ideas for a given story element.
    
    Args:
        topic: What to brainstorm about (e.g., "plot twist", "character backstory", "magical system")
        genre: Story genre
        tone: Story tone
        context: Current story context
        author: Optional author style to emulate
        author_style_guidance: Optional guidance on author's style
        num_ideas: Number of ideas to generate
        evaluation_criteria: List of criteria to evaluate ideas against
        
    Returns:
        Dictionary with generated ideas and evaluations
    """
    if evaluation_criteria is None:
        evaluation_criteria = [
            "Originality and surprise factor",
            "Coherence with the established narrative",
            "Potential for character development",
            "Reader engagement and emotional impact",
            "Feasibility within the story world"
        ]
        
    # Prepare author style guidance if provided
    style_section = ""
    if author and author_style_guidance:
        style_section = f"""
        AUTHOR STYLE CONSIDERATION:
        Consider the writing style of {author} as you generate ideas:
        
        {author_style_guidance}
        
        The ideas should feel like they could appear in a story by this author.
        """
    
    # Brainstorming prompt
    brainstorm_prompt = f"""
    # Creative Brainstorming Session: {topic}
    
    ## Context
    - Genre: {genre}
    - Tone: {tone}
    - Current Story Context: {context}
    {style_section}
    
    ## Instructions
    Generate {num_ideas} diverse, creative ideas related to {topic}.
    Think outside the box while maintaining coherence with the story context.
    Each idea should be surprising yet plausible within the established world.
    
    For each idea:
    1. Provide a concise title/headline
    2. Describe the idea in 3-5 sentences
    3. Note one potential benefit to the story
    4. Note one potential challenge to implementation
    
    Format each idea clearly and number them 1 through {num_ideas}.
    """
    
    # Generate ideas
    ideas_response = llm.invoke([HumanMessage(content=brainstorm_prompt)]).content
    
    # Evaluation prompt
    eval_prompt = f"""
    # Idea Evaluation for: {topic}
    
    ## Ideas Generated
    {ideas_response}
    
    ## Story Context
    {context}
    
    ## Evaluation Criteria
    {', '.join(evaluation_criteria)}
    
    ## Instructions
    Evaluate each idea against the criteria above on a scale of 1-10.
    For each idea:
    1. Provide scores for each criterion
    2. Calculate a total score
    3. Write a brief justification (2-3 sentences)
    4. Indicate if the idea should be incorporated (YES/MAYBE/NO)
    
    Then rank the ideas from best to worst fit for the story.
    Finally, recommend the top 1-2 ideas to incorporate, with brief reasoning.
    """
    
    # Evaluate ideas
    evaluation = llm.invoke([HumanMessage(content=eval_prompt)]).content
    
    # Store brainstorming results in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": f"brainstorm_{topic.lower().replace(' ', '_')}",
        "value": {
            "ideas": ideas_response,
            "evaluation": evaluation,
            "timestamp": "now",
            "topic": topic
        },
        "namespace": MEMORY_NAMESPACE
    })
    
    # Return results
    return {
        "ideas": ideas_response,
        "evaluation": evaluation,
        "recommended_ideas": evaluation.split("recommend")[-1].strip() if "recommend" in evaluation.lower() else None
    }

def parse_structured_data(text, default_data=None):
    """Parse structured data from text, with fallback to default data."""
    try:
        # Clean the response to handle potential markdown formatting
        clean_json_str = text
        if "```json" in clean_json_str:
            clean_json_str = clean_json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_json_str:
            clean_json_str = clean_json_str.split("```")[1].split("```")[0].strip()
            
        return json.loads(clean_json_str)
    except json.JSONDecodeError:
        print("Failed to parse JSON. Using fallback data.")
        return default_data if default_data else {}