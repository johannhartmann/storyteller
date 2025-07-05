"""
Intelligent worldbuilding selection for scene integration.

This module provides semantic, LLM-based selection of relevant worldbuilding
elements for each scene, avoiding brittle keyword matching.
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from pydantic import BaseModel, Field

from storyteller_lib.core.config import llm, DEFAULT_LANGUAGE
from storyteller_lib.core.logger import get_logger
from storyteller_lib.persistence.database import get_db_manager
from storyteller_lib.prompts.renderer import get_prompt_template, render_prompt

logger = get_logger(__name__)


class WorldbuildingSelection(BaseModel):
    """A selected worldbuilding element."""

    content: str = Field(
        description="The relevant worldbuilding content for this scene"
    )


class WorldbuildingSelections(BaseModel):
    """Collection of selected worldbuilding elements for a scene."""

    selections: List[WorldbuildingSelection] = Field(
        description="Selected worldbuilding elements ordered by relevance"
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
        self._language = None
        if not self.db_manager:
            logger.error("Database manager not available in WorldbuildingSelector!")
        elif not self.db_manager._db:
            logger.error("Database manager has no database connection!")
        else:
            logger.info("WorldbuildingSelector initialized with database connection")
            # Try to load worldbuilding immediately to test
            test_wb = self.get_all_worldbuilding()
            logger.info(
                f"Test load on init: {len(test_wb)} categories, {sum(len(v) for v in test_wb.values())} elements"
            )

    def _get_language(self) -> str:
        """Get the language from the database config."""
        if self._language is None:
            self._language = DEFAULT_LANGUAGE
            if self.db_manager and self.db_manager._db:
                with self.db_manager._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT language FROM story_config WHERE id = 1")
                    result = cursor.fetchone()
                    if result and result["language"]:
                        self._language = result["language"]
        return self._language

    def refresh_worldbuilding_cache(self):
        """Force refresh the worldbuilding cache from database."""
        self._worldbuilding_cache = None
        logger.info("Cleared worldbuilding cache, will reload on next access")

    def get_all_worldbuilding(self) -> Dict[str, Dict[str, str]]:
        """Retrieve all worldbuilding from database."""
        # If cache exists and has content, return it
        if self._worldbuilding_cache is not None and self._worldbuilding_cache:
            return self._worldbuilding_cache

        # If cache is empty or None, try to load from database
        logger.info("Loading worldbuilding from database (cache miss or empty)")

        worldbuilding = {}

        if not self.db_manager:
            logger.error("No database manager available!")
            return {}

        if not self.db_manager._db:
            logger.error("Database manager has no database connection!")
            return {}

        try:
            with self.db_manager._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT category, element_key, element_value
                    FROM world_elements
                    ORDER BY category, element_key
                """
                )

                rows = cursor.fetchall()
                logger.info(f"Found {len(rows)} worldbuilding elements in database")

                if not rows:
                    logger.warning(
                        "No worldbuilding elements found in world_elements table!"
                    )

                for row in rows:
                    category = row["category"]
                    if category not in worldbuilding:
                        worldbuilding[category] = {}
                    worldbuilding[category][row["element_key"]] = row["element_value"]
                    logger.debug(
                        f"Loaded {category}.{row['element_key']}: {row['element_value'][:50]}..."
                    )
        except Exception as e:
            logger.error(
                f"Failed to load worldbuilding from database: {str(e)}", exc_info=True
            )
            return {}

        self._worldbuilding_cache = worldbuilding
        logger.info(
            f"Loaded worldbuilding from database: {len(worldbuilding)} categories, "
            f"{sum(len(v) for v in worldbuilding.values())} total elements"
        )
        return worldbuilding

    def select_relevant_elements(
        self, scene_context: SceneContext, max_elements: int = 7
    ) -> WorldbuildingSelections:
        """Select the most relevant worldbuilding elements for the scene."""
        # Get worldbuilding directly from database
        wb_summary = []

        if not self.db_manager or not self.db_manager._db:
            logger.error("No database connection available")
            return WorldbuildingSelections(selections=[])

        try:
            # Debug database connection
            logger.info(f"DB Manager: {self.db_manager}")
            logger.info(f"DB Manager._db: {self.db_manager._db}")
            if self.db_manager._db:
                logger.info(f"DB path: {self.db_manager._db.db_path}")

            with self.db_manager._db._get_connection() as conn:
                cursor = conn.cursor()

                # First check if table exists
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='world_elements'"
                )
                table_exists = cursor.fetchone()
                logger.info(f"world_elements table exists: {table_exists is not None}")

                cursor.execute(
                    """
                    SELECT category, element_key, element_value
                    FROM world_elements
                    ORDER BY category, element_key
                """
                )

                rows = cursor.fetchall()
                logger.info(f"Loading {len(rows)} worldbuilding elements for selection")

                current_category = None
                for row in rows:
                    category = row["category"]
                    if category != current_category:
                        current_category = category
                        wb_summary.append(f"\n{category.upper()}:")
                        wb_summary.append("=" * 50)

                    wb_summary.append(f"\n[{category}/{row['element_key']}]")
                    wb_summary.append(row["element_value"].strip())
                    wb_summary.append("")  # Empty line between elements

                wb_content = "\n".join(wb_summary)
                logger.info(
                    f"Created worldbuilding summary with {len(wb_content)} chars"
                )

        except Exception as e:
            logger.error(
                f"Failed to load worldbuilding from database: {str(e)}", exc_info=True
            )
            return WorldbuildingSelections(selections=[])

        prompt = render_prompt(
            "select_worldbuilding_elements",
            language=self._get_language(),
            scene_description=scene_context.description,
            location=scene_context.location,
            scene_type=scene_context.scene_type,
            dramatic_purpose=scene_context.dramatic_purpose,
            characters=scene_context.characters,
            plot_threads=scene_context.plot_threads,
            chapter_themes=scene_context.chapter_themes,
            wb_summary=wb_content,
            max_elements=max_elements,
        )

        try:
            structured_llm = llm.with_structured_output(WorldbuildingSelections)
            selections = structured_llm.invoke(prompt)

            logger.info(f"Selected {len(selections.selections)} worldbuilding elements")
            return selections
        except Exception as e:
            logger.error(
                f"Failed to select worldbuilding elements: {str(e)}", exc_info=True
            )
            # Return empty selections rather than failing completely
            return WorldbuildingSelections(selections=[])

    def extract_relevant_snippets(
        self, selections: WorldbuildingSelections, scene_context: SceneContext
    ) -> List[str]:
        """Extract only the relevant portions of selected worldbuilding."""
        return [selection.content for selection in selections.selections]

    def _create_worldbuilding_summary(
        self, worldbuilding: Dict[str, Dict[str, str]]
    ) -> str:
        """Create a COMPLETE listing of all available worldbuilding elements with full content."""
        summary_lines = []

        for category, elements in worldbuilding.items():
            if elements:
                summary_lines.append(f"\n{category.upper()}:")
                summary_lines.append("=" * 50)

                for key, content in elements.items():
                    # Include FULL content, not just a preview
                    summary_lines.append(f"\n[{category}/{key}]")
                    summary_lines.append(content.strip())
                    summary_lines.append("")  # Empty line between elements

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
        previous_scene_summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Main entry point for selecting worldbuilding for a scene."""
        logger.info(
            f"=== Starting worldbuilding selection for Chapter {chapter}, Scene {scene} ==="
        )

        # Check if we have worldbuilding data
        all_wb = self.get_all_worldbuilding()
        if not all_wb:
            logger.warning("No worldbuilding data found in database!")
            return {"elements": [], "selection_count": 0}

        # Create scene context
        scene_context = SceneContext(
            description=scene_description,
            scene_type=scene_type,
            location=location,
            characters=characters,
            plot_threads=plot_threads,
            dramatic_purpose=dramatic_purpose,
            chapter_themes=chapter_themes,
            previous_scene_summary=previous_scene_summary,
        )

        try:
            # Direct selection of relevant elements
            logger.info("Selecting relevant worldbuilding elements...")
            selections = self.select_relevant_elements(scene_context)
            logger.info(f"Selected {len(selections.selections)} worldbuilding elements")

            # Extract just the content
            snippets = self.extract_relevant_snippets(selections, scene_context)

            logger.info(f"Successfully selected {len(snippets)} worldbuilding elements")

            return {
                "elements": snippets,  # Just return the list of content strings
                "selection_count": len(snippets),
            }
        except Exception as e:
            logger.error(f"Error in worldbuilding selection: {str(e)}", exc_info=True)
            return {"elements": [], "selection_count": 0}


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
    scene: int,
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
        chapter_themes=chapter_themes,
    )
