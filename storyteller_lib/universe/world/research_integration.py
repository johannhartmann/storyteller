"""
Integration module for research-driven world building.

This module provides the enhanced world building function that integrates
research capabilities while maintaining backward compatibility.
"""

import asyncio
from typing import Dict, Any, Optional, Type
from pydantic import BaseModel

from storyteller_lib.core.models import StoryState
from storyteller_lib.core.config import llm, get_story_config, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from storyteller_lib.core.logger import get_logger
from storyteller_lib.persistence.database import get_db_manager
from storyteller_lib.prompts.renderer import render_prompt
from storyteller_lib import track_progress

from storyteller_lib.universe.world.builder import (
    Geography, History, Culture, Politics, Economics,
    TechnologyMagic, Religion, DailyLife,
    generate_category, generate_mystery_elements,
    generate_world_summary
)
from storyteller_lib.universe.world.research_config import WorldBuildingResearchConfig
from storyteller_lib.universe.world.researcher import WorldBuildingResearcher
from storyteller_lib.universe.world.research_models import ResearchContext, ResearchResults

from langchain_core.messages import AIMessage, RemoveMessage

logger = get_logger(__name__)


async def generate_category_with_research(
    category_name: str,
    model: Type[BaseModel],
    genre: str,
    tone: str,
    author: str,
    initial_idea: str,
    global_story: str,
    research_results: Optional[ResearchResults] = None,
    language: str = DEFAULT_LANGUAGE,
    language_guidance: str = "",
) -> Dict[str, Any]:
    """
    Generate a category with research context.
    
    Args:
        category_name: Name of the category
        model: Pydantic model for the category
        genre: Story genre
        tone: Story tone
        author: Author style
        initial_idea: Initial story idea
        global_story: Story outline
        research_results: Research findings for this category
        language: Target language
        language_guidance: Language-specific guidance
        
    Returns:
        Generated category data
    """
    # If no research results, fall back to original generation
    if not research_results:
        return generate_category(
            category_name, model, genre, tone, author,
            initial_idea, global_story, language, language_guidance
        )
    
    # Create research-informed prompt
    research_context = ""
    if research_results.synthesized_insights:
        insights = "\n".join([
            f"- {key}: {value}"
            for key, value in research_results.synthesized_insights.items()
        ])
        research_context += f"\nResearch Insights:\n{insights}\n"
    
    if research_results.relevant_examples:
        examples = "\n".join([
            f"- {ex['title']}: {ex['description']}"
            for ex in research_results.relevant_examples[:5]
        ])
        research_context += f"\nReal-world Examples:\n{examples}\n"
    
    if research_results.research_summary:
        research_context += f"\nResearch Summary:\n{research_results.research_summary}\n"
    
    # Use structured output with research context
    structured_llm = llm.with_structured_output(model)
    
    try:
        # Try to use a research-specific template
        prompt = render_prompt(
            f"worldbuilding_research_{category_name.lower()}",
            language=language,
            story_outline=global_story,
            genre=genre,
            tone=tone,
            category_name=category_name,
            initial_idea=initial_idea,
            author=author,
            research_context=research_context,
            research_insights=research_results.synthesized_insights,
            research_examples=research_results.relevant_examples
        )
    except:
        # Fall back to regular template with research added
        try:
            prompt = render_prompt(
                "worldbuilding",
                language=language,
                story_outline=global_story,
                genre=genre,
                tone=tone,
                category_name=category_name,
                initial_idea=initial_idea,
                author=author,
                existing_elements=research_context
            )
        except:
            # Ultimate fallback
            prompt = f"""
            Generate {category_name} elements for a {genre} story with a {tone} tone,
            written in the style of {author}, based on this initial idea:
            
            {initial_idea}
            
            Story outline: {global_story}
            
            {research_context}
            
            Use the research insights to create authentic, grounded {category_name} elements
            that feel real and detailed. Include all required fields for the category.
            """
    
    result = structured_llm.invoke(prompt)
    data = result.model_dump()
    
    # Add research citations if enabled
    if research_results and research_results.source_citations:
        data["research_sources"] = [
            {
                "name": cite.source_name,
                "url": cite.source_url,
                "relevance": cite.relevance_score
            }
            for cite in research_results.source_citations[:5]
        ]
    
    return data


@track_progress
async def generate_worldbuilding_with_research(state: StoryState) -> Dict:
    """
    Enhanced world building with optional research.
    
    This function extends the original world building to support
    research-driven generation while maintaining backward compatibility.
    """
    # Load configuration
    config = get_story_config()
    research_config = WorldBuildingResearchConfig.from_config(config)
    
    genre = config["genre"]
    tone = config["tone"] 
    author = config["author"]
    initial_idea = config["initial_idea"]
    
    # Get story outline from database
    db_manager = get_db_manager()
    if not db_manager or not db_manager._db:
        raise RuntimeError("Database manager not available")
    
    logger.debug("Fetching global story from database")
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, global_story FROM story_config WHERE id = 1"
        )
        result = cursor.fetchone()
        
        if not result:
            raise RuntimeError("Story configuration not found in database")
        
        global_story = result["global_story"]
        if not global_story:
            raise RuntimeError("Story outline is empty in database")
    
    # Get language settings
    language = state.get("language", DEFAULT_LANGUAGE)
    language_guidance = ""  # Will be set if needed
    
    # Define category models
    category_models = {
        "geography": Geography,
        "history": History,
        "culture": Culture,
        "politics": Politics,
        "economics": Economics,
        "technology_magic": TechnologyMagic,
        "religion": Religion,
        "daily_life": DailyLife,
    }
    
    world_elements = {}
    
    if research_config.enable_research:
        logger.info("Using research-driven world building")
        
        # Initialize researcher
        researcher = WorldBuildingResearcher(research_config)
        
        # Create research context
        context = ResearchContext(
            genre=genre,
            tone=tone,
            initial_idea=initial_idea,
            story_outline=global_story,
            language=language,
            time_period=config.get("time_period"),
            cultural_context=config.get("cultural_context")
        )
        
        # Phase 1: Initial context research
        logger.info("Conducting initial context research")
        initial_research = await researcher.research_initial_context(
            genre=genre,
            tone=tone,
            initial_idea=initial_idea,
            story_outline=global_story
        )
        
        # Phase 2: Research each category
        if research_config.parallel_research:
            # Parallel research for all categories
            research_tasks = []
            for category in category_models.keys():
                task = researcher.research_category(
                    category=category,
                    context=context,
                    existing_research=initial_research
                )
                research_tasks.append((category, task))
            
            # Execute all research in parallel
            category_research = {}
            results = await asyncio.gather(
                *[task for _, task in research_tasks],
                return_exceptions=True
            )
            
            for (category, _), result in zip(research_tasks, results):
                if isinstance(result, Exception):
                    logger.error(f"Research failed for {category}: {str(result)}")
                    category_research[category] = None
                else:
                    category_research[category] = result
        else:
            # Sequential research
            category_research = {}
            for category in category_models.keys():
                try:
                    research_result = await researcher.research_category(
                        category=category,
                        context=context,
                        existing_research={
                            "initial": initial_research,
                            "categories": world_elements
                        }
                    )
                    category_research[category] = research_result
                except Exception as e:
                    logger.error(f"Research failed for {category}: {str(e)}")
                    category_research[category] = None
        
        # Phase 3: Generate categories with research
        for category_name, model in category_models.items():
            logger.info(f"Generating {category_name} with research context")
            
            try:
                category_data = await generate_category_with_research(
                    category_name=category_name,
                    model=model,
                    genre=genre,
                    tone=tone,
                    author=author,
                    initial_idea=initial_idea,
                    global_story=global_story,
                    research_results=category_research.get(category_name),
                    language=language,
                    language_guidance=language_guidance
                )
                world_elements[category_name] = category_data
            except Exception as e:
                logger.error(f"Failed to generate {category_name}: {str(e)}")
                # Fall back to non-research generation
                category_data = generate_category(
                    category_name, model, genre, tone, author,
                    initial_idea, global_story, language, language_guidance
                )
                world_elements[category_name] = category_data
    
    else:
        # Non-research mode - use original generation
        logger.info("Using standard world building (research disabled)")
        
        for category_name, model in category_models.items():
            logger.info(f"Generating {category_name} elements...")
            category_data = generate_category(
                category_name, model, genre, tone, author,
                initial_idea, global_story, language, language_guidance
            )
            world_elements[category_name] = category_data
    
    # Generate mystery elements (same for both modes)
    mystery_elements = generate_mystery_elements(world_elements, 3, language)
    
    # Create world state tracker
    world_state_tracker = {
        "initial_state": world_elements,
        "current_state": world_elements,
        "changes": [],
        "revelations": [],
        "mystery_elements": {
            "key_mysteries": mystery_elements.get("key_mysteries", []),
            "clues_revealed": {},
            "reader_knowledge": {},
            "character_knowledge": {},
        },
    }
    
    # Generate world summary
    world_summary = generate_world_summary(world_elements, genre, tone, language)
    
    # Store in database
    if db_manager:
        try:
            db_manager.save_worldbuilding(world_elements)
            logger.info("World elements stored in database")
        except Exception as e:
            logger.warning(f"Could not store world elements: {e}")
    
    # Log progress
    from storyteller_lib.utils.progress_logger import log_progress
    log_progress("world_elements", world_elements=world_elements)
    
    # Return state update
    research_note = ""
    if research_config.enable_research:
        research_note = " The world has been enriched with real-world research to ensure authenticity and depth."
    
    return {
        "world_elements": {"stored_in_db": True},
        "messages": [
            *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
            AIMessage(
                content=f"I've created detailed worldbuilding elements for your {genre} story with a {tone} tone.{research_note} The world includes geography, history, culture, politics, economics, technology/magic, religion, and daily life elements that will support your story.\n\nWorld Summary:\n{world_summary}"
            ),
        ],
    }