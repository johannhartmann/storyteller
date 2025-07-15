#!/usr/bin/env python
"""
Run the StoryCraft agent to generate a complete story with progress updates.
Uses a simple sequential orchestrator for reliable story generation.
"""

# Standard library imports
import argparse
import logging.config
import os
import sys
from typing import Any

# Third party imports
from dotenv import load_dotenv

# Local imports
# Progress tracking removed - using logging instead
from storyteller_lib.analysis.statistics import display_progress_report
from storyteller_lib.api.storyteller import generate_story_simplified
from storyteller_lib.core.config import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from storyteller_lib.core.logger import setup_logging
# Progress tracking removed - using logging instead
from storyteller_lib.utils.info import save_story_info

setup_logging(level="DEBUG", log_file="storyteller_debug.log")

# Load environment variables from .env file
load_dotenv()

# Configure logging to suppress httpx messages
if os.path.exists("logging.conf"):
    logging.config.fileConfig("logging.conf")
else:
    # Fallback if config file not found - at least silence httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)

# Progress tracking removed - using logging instead


def write_scene_to_file(chapter_num: int, scene_num: int, output_file: str) -> None:
    """
    Write a single scene to the output file.

    Args:
        chapter_num: The chapter number
        scene_num: The scene number
        output_file: The output file path
    """
    try:
        # Get content from database
        from storyteller_lib.persistence.database import get_db_manager

        db_manager = get_db_manager()

        if not db_manager or not db_manager._db:
            print(
                f"Error: Database manager not available for Scene {scene_num} of Chapter {chapter_num}"
            )
            return

        # Get scene content from database
        content = db_manager.get_scene_content(chapter_num, scene_num)
        if not content:
            print(
                f"Error: No content found for Scene {scene_num} of Chapter {chapter_num}"
            )
            return

        # Ensure the directory exists
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Check if the file exists and if we need to add headers
        file_exists = os.path.exists(output_file)
        needs_story_title = (
            not file_exists or os.path.getsize(output_file) < 300
        )  # Less than error message size

        # Check if this chapter header has been written
        chapter_header_written = False
        if file_exists and os.path.getsize(output_file) > 300:
            with open(output_file) as f:
                existing_content = f.read()
                chapter_header_written = (
                    f"## Chapter {chapter_num}:" in existing_content
                )

        # Open the file in append mode
        with open(output_file, "a" if file_exists else "w") as f:
            # If this is a new file or very small (error message), add a title
            if needs_story_title:
                # Get story info from database
                with db_manager._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT title, genre, tone, global_story FROM story_config WHERE id = 1"
                    )
                    story_info = cursor.fetchone()
                    if story_info:
                        story_title = story_info["title"]
                        # If title is still the placeholder, try to extract from global_story
                        if (
                            not story_title
                            or story_title
                            == f"{story_info['tone'].title()} {story_info['genre'].title()} Story"
                            or "Story" in story_title
                            and len(story_title) < 30
                        ):
                            print(
                                f"[DEBUG] Title in DB is placeholder: '{story_title}', attempting to extract from outline"
                            )
                            if story_info["global_story"]:
                                # Re-extract the title
                                from storyteller_lib.persistence.database import (
                                    StoryDatabaseManager,
                                )

                                temp_manager = StoryDatabaseManager()
                                extracted_title = (
                                    temp_manager._extract_title_from_outline(
                                        story_info["global_story"]
                                    )
                                )
                                if (
                                    extracted_title
                                    and extracted_title != "Untitled Story"
                                ):
                                    story_title = extracted_title
                                    print(
                                        f"[DEBUG] Re-extracted title: '{story_title}'"
                                    )
                                    # Update the database with the correct title
                                    cursor.execute(
                                        "UPDATE story_config SET title = ? WHERE id = 1",
                                        (story_title,),
                                    )
                                    conn.commit()
                        print(f"[DEBUG] Using story title: '{story_title}'")
                    else:
                        story_title = "Generated Story"
                        print("[DEBUG] No story_config found, using default title")

                # Clear any error message and write title
                f.seek(0)
                f.truncate()
                f.write(f"# {story_title}\n\n")

            # Write chapter header if this is the first scene of the chapter
            if not chapter_header_written and scene_num == 1:
                # Get chapter title from database
                with db_manager._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT title FROM chapters WHERE chapter_number = ?",
                        (chapter_num,),
                    )
                    result = cursor.fetchone()
                    if result and result["title"]:
                        chapter_title = result["title"]
                        print(f"[DEBUG] Found chapter title in DB: '{chapter_title}'")
                    else:
                        chapter_title = f"Chapter {chapter_num}"
                        print("[DEBUG] No chapter title in DB, using default")
                f.write(f"\n## Chapter {chapter_num}: {chapter_title}\n\n")

            # Write scene title
            f.write(f"### Scene {scene_num}\n\n")

            # Write the scene content
            f.write(content)
            f.write("\n\n")

        print(
            f"Scene {scene_num} of Chapter {chapter_num} successfully written to {output_file}"
        )

    except Exception as e:
        print(
            f"Error writing scene {scene_num} of chapter {chapter_num} to {output_file}: {str(e)}"
        )
        import traceback

        traceback.print_exc()


def write_chapter_to_file(
    chapter_num: int, chapter_data: dict[str, Any], output_file: str
) -> None:
    """
    Write a completed chapter to the output file.

    Args:
        chapter_num: The chapter number
        chapter_data: The chapter data
        output_file: The output file path
    """
    try:
        # Convert chapter_num to int if it's a string
        if isinstance(chapter_num, str):
            chapter_num = int(chapter_num)

        # Get content from database since we're using thin state pattern
        from storyteller_lib.persistence.database import get_db_manager

        db_manager = get_db_manager()

        if not db_manager or not db_manager._db:
            print(f"Error: Database manager not available for Chapter {chapter_num}")
            return

        # Get chapter title from database
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT title FROM chapters WHERE chapter_number = ?", (chapter_num,)
            )
            result = cursor.fetchone()
            chapter_title = result["title"] if result else f"Chapter {chapter_num}"

        # Ensure the directory exists
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Check if the file exists
        file_exists = os.path.exists(output_file)

        # Open the file in append mode if it exists, otherwise in write mode
        mode = "a" if file_exists else "w"

        with open(output_file, mode) as f:
            # If this is a new file, add a title
            if not file_exists:
                # Try to get the actual title from the database
                story_title = "Generated Story"  # Default
                try:
                    with db_manager._db._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT title FROM story_config WHERE id = 1")
                        result = cursor.fetchone()
                        if result and result["title"]:
                            story_title = result["title"]
                except Exception:
                    pass  # Use default title if database query fails

                f.write(f"# {story_title}\n\n")

            # Write the chapter title
            f.write(f"\n## Chapter {chapter_num}: {chapter_title}\n\n")

            # Get all scenes for this chapter from database
            with db_manager._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT s.scene_number, s.content
                    FROM scenes s
                    JOIN chapters c ON s.chapter_id = c.id
                    WHERE c.chapter_number = ?
                    ORDER BY s.scene_number
                """,
                    (chapter_num,),
                )

                scenes = cursor.fetchall()

            if not scenes:
                f.write("*No scenes available for this chapter*\n\n")
            else:
                for scene in scenes:
                    scene_num = scene["scene_number"]
                    content = scene["content"]
                    if content:
                        f.write(content)
                        f.write("\n\n")
                    else:
                        f.write(f"*Scene {scene_num} content not available*\n\n")

        print(f"Chapter {chapter_num} successfully written to {output_file}")
    except OSError as e:
        print(f"Error writing chapter {chapter_num} to {output_file}: {str(e)}")


# Progress callback removed - using logging instead
def get_story_title_from_db() -> str | None:
    """Get the story title from the database."""
    try:
        from storyteller_lib.persistence.database import get_db_manager

        db_manager = get_db_manager()

        if db_manager and db_manager._db:
            with db_manager._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT title FROM story_config WHERE id = 1")
                result = cursor.fetchone()
                if result and result["title"]:
                    return result["title"]
    except Exception:
        pass
    return None


def sanitize_filename(title: str) -> str:
    """Convert a story title to a valid filename."""
    import re

    # Replace spaces and invalid filename characters with underscores
    # Keep Unicode letters, numbers, dashes, and common international characters
    filename = re.sub(r"[^\w\-äöüÄÖÜßéèêàâçñáíóúÁÍÓÚ]+", "_", title, flags=re.UNICODE)
    # Remove multiple consecutive underscores
    filename = re.sub(r"_+", "_", filename)
    # Remove leading/trailing underscores
    filename = filename.strip("_")
    # Ensure we have a valid filename
    if not filename:
        filename = "untitled_story"
    return filename


def main() -> None:
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Generate a story using the refactored StoryCraft agent"
    )
    parser.add_argument(
        "--genre",
        type=str,
        default="fantasy",
        help="Genre of the story (e.g., fantasy, sci-fi, mystery)",
    )
    parser.add_argument(
        "--tone",
        type=str,
        default="epic",
        help="Tone of the story (e.g., epic, dark, humorous)",
    )
    parser.add_argument(
        "--author",
        type=str,
        default="",
        help="Author whose style to emulate (e.g., Tolkien, Rowling, Martin)",
    )
    parser.add_argument(
        "--language",
        type=str,
        default=DEFAULT_LANGUAGE,
        help=f"Target language for story generation (e.g., {', '.join(SUPPORTED_LANGUAGES.keys())})",
    )
    parser.add_argument(
        "--idea",
        type=str,
        default="",
        help="Initial story idea to use as a starting point (e.g., 'A detective story set in a zoo')",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="story.md",
        help="Output file to save the generated story",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Display detailed information about the story elements as they're generated",
    )
    # Add model provider options
    from storyteller_lib.core.config import (
        DEFAULT_MODEL_PROVIDER,
        MODEL_CONFIGS,
        MODEL_PROVIDER_OPTIONS,
    )

    parser.add_argument(
        "--model-provider",
        type=str,
        choices=MODEL_PROVIDER_OPTIONS,
        default=DEFAULT_MODEL_PROVIDER,
        help=f"LLM provider to use (default: {DEFAULT_MODEL_PROVIDER})",
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Specific model to use (defaults to provider's default model)",
    )
    # Add narrative structure options
    parser.add_argument(
        "--structure",
        type=str,
        default="auto",
        choices=[
            "auto",
            "hero_journey",
            "three_act",
            "kishotenketsu",
            "in_medias_res",
            "circular",
            "nonlinear_mosaic",
        ],
        help="Narrative structure to use (default: auto - let AI choose based on genre/tone)",
    )
    parser.add_argument(
        "--pages",
        type=int,
        help="Target number of pages for the story (e.g., 200 for a short novel, 400 for standard)",
    )
    parser.add_argument(
        "--progress-log",
        type=str,
        help="Path to save progress log file (default: automatically generated in ~/.storyteller/logs/)",
    )
    parser.add_argument(
        "--audio-book",
        action="store_true",
        help="Generate SSML-formatted audiobook version of the story (during or after generation)",
    )
    parser.add_argument(
        "--research-worldbuilding",
        action="store_true",
        help="Use web research to create more authentic world building (requires TAVILY_API_KEY)",
    )
    args = parser.parse_args()

    # Import config to check API keys

    # Check if API key is set for the selected provider
    provider = args.model_provider
    api_key_env = MODEL_CONFIGS[provider]["env_key"]
    if not os.environ.get(api_key_env):
        print(
            f"Error: {api_key_env} environment variable is not set for the {provider} provider."
        )
        print(f"Please create a .env file with {api_key_env}=your_api_key")
        return

    # Check if TAVILY_API_KEY is set when research is enabled
    if args.research_worldbuilding and not os.environ.get("TAVILY_API_KEY"):
        print("Error: TAVILY_API_KEY environment variable is not set.")
        print("Research-based worldbuilding requires a Tavily API key.")
        print("Please add TAVILY_API_KEY=your_key to your .env file")
        print("Get your API key at: https://app.tavily.com/")
        return

    # Progress tracking removed - using logging instead

    # Set up caching based on environment variables
    from storyteller_lib.core.config import CACHE_LOCATION, setup_cache

    # Get cache type from environment
    cache_type = os.environ.get("CACHE_TYPE", "sqlite")

    # Setup the cache with the specified type
    cache = setup_cache(cache_type)
    print(f"LLM caching: {cache_type}")
    print(f"Cache location: {CACHE_LOCATION}")

    # Database path is handled by environment variable
    from storyteller_lib.core.config import DATABASE_PATH

    print(f"Database persistence: {DATABASE_PATH}")

    # Handle SSML conversion for existing story (if audio-book flag is set without generating new story)
    if args.audio_book and not any([args.genre, args.tone, args.idea]):
        # User wants to convert existing story to audiobook
        try:
            print("Converting existing story to SSML format for audiobook...")
            from storyteller_lib.audiobook.ssml.converter import SSMLConverter
            from storyteller_lib.core.config import DATABASE_PATH

            # Check if database exists
            if not os.path.exists(DATABASE_PATH):
                print(f"Error: No story database found at {DATABASE_PATH}")
                print("Please generate a story first before converting to audiobook.")
                return

            # Create SSML converter
            ssml_converter = SSMLConverter(
                model_provider=args.model_provider,
                model=args.model,
                language=args.language,
            )

            # Get story title for output filename
            story_title = get_story_title_from_db()
            if story_title:
                output_filename = f"{sanitize_filename(story_title)}_audiobook.ssml"
            else:
                output_filename = "story_audiobook.ssml"

            # Convert to SSML
            ssml_converter.convert_book_to_ssml(DATABASE_PATH, output_filename)

            print("\nSSML conversion complete!")
            print(f"SSML file saved to: {output_filename}")
            print("\nTo generate audio files, run:")
            print("  nix develop -c python generate_audiobook.py")
            return

        except Exception as e:
            print(f"Error converting to audiobook: {str(e)}")
            import traceback

            traceback.print_exc()
            return

    try:
        # Single story mode - always starts fresh

        # Delete existing database to ensure a fresh start
        from storyteller_lib.core.config import DATABASE_PATH

        if os.path.exists(DATABASE_PATH):
            os.unlink(DATABASE_PATH)
            print("Removed existing database to start fresh")

        # Reinitialize database manager with fresh database
        from storyteller_lib.persistence.database import initialize_db_manager

        initialize_db_manager(DATABASE_PATH)

        # Generate the story with visual progress display
        author_str = f" in the style of {args.author}" if args.author else ""
        language_str = (
            f" in {SUPPORTED_LANGUAGES.get(args.language.lower(), args.language)}"
            if args.language.lower() != DEFAULT_LANGUAGE
            else ""
        )

        # Get model information
        from storyteller_lib.core.config import MODEL_CONFIGS

        provider_config = MODEL_CONFIGS[args.model_provider]
        model_name = args.model or provider_config["default_model"]

        print(
            f"Generating a {args.tone} {args.genre} story{author_str}{language_str}..."
        )
        print(f"Using {args.model_provider.upper()} model: {model_name}")
        print("This will take some time. Progress updates will be displayed below:")

        # Progress tracking removed - using logging instead

        # Progress tracking removed - using logging instead
        # reset_progress_tracking()
        # set_progress_callback(progress_callback)

        story = None
        partial_story = None
        import time
        start_time = time.time()
        try:
            # Start the story generation
            # Get recursion limit from environment
            recursion_limit = int(os.environ.get("LANGGRAPH_RECURSION_LIMIT", "200"))

            story, state = generate_story_simplified(
                genre=args.genre,
                tone=args.tone,
                author=args.author,
                initial_idea=args.idea,
                language=args.language,
                progress_log_path=args.progress_log,
                narrative_structure=args.structure,
                target_pages=args.pages,
                recursion_limit=recursion_limit,
                research_worldbuilding=args.research_worldbuilding,
            )

            # Show completion message
            elapsed_time = time.time() - start_time
            elapsed_str = f"{int(elapsed_time // 60)}m {int(elapsed_time % 60)}s"
            print(f"[{elapsed_str}] Story generation complete!")

            # If using default output filename, try to use the story title
            if args.output == "story.md":
                story_title = get_story_title_from_db()
                if story_title:
                    sanitized_title = sanitize_filename(story_title)
                    args.output = f"{sanitized_title}.md"
                    print(f"Using story title for filename: {args.output}")
        except Exception as e:
            # Show error message with elapsed time
            elapsed_time = time.time() - start_time
            elapsed_str = f"{int(elapsed_time // 60)}m {int(elapsed_time % 60)}s"
            print(f"[{elapsed_str}] Error during story generation: {str(e)}")
            import traceback

            traceback.print_exc()

            # Try to recover partial story from database
            try:
                print("Attempting to recover partial story...")
                from storyteller_lib.persistence.database import get_db_manager

                db_manager = get_db_manager()
                if db_manager:
                    partial_story = db_manager.compile_story()
                    if partial_story:
                        print("Partial story recovered successfully!")
                        story = partial_story

                        # Always generate info file
                        try:
                            # Create a minimal state for info file
                            state = {
                                "chapters": {},
                                "characters": {},
                                "world_elements": {},
                            }
                            info_file = save_story_info(state, args.output)
                            print(f"Partial story information saved to {info_file}")
                        except Exception as info_err:
                            print(
                                f"Error saving partial story information: {str(info_err)}"
                            )
            except Exception as recovery_err:
                print(f"Could not recover partial story: {str(recovery_err)}")

        # Ensure we have a story to save
        if story is None:
            print("No story was generated. Please check the error messages above.")
            # Create a minimal story that explains the error
            title = (
                f"Incomplete {args.tone.capitalize()} {args.genre.capitalize()} Story"
            )
            story = f"# {title}\n\n"
            story += "## Error During Generation\n\n"
            story += "This story could not be fully generated due to an error in the workflow.\n\n"
            story += (
                "Please check the console output for error details and try again.\n\n"
            )
            print("Created minimal error-explaining story file instead.")

        # Ensure the output has proper markdown formatting
        if not story.startswith("# "):
            # Add a title if not already present
            story = f"# Generated {args.tone.capitalize()} {args.genre.capitalize()} Story\n\n{story}"

        # Make sure chapters are properly formatted with markdown headers
        import re

        # Find chapter headings that aren't already markdown headers
        story = re.sub(
            r"(?<!\n\n)Chapter (\d+): ([^\n]+)(?!\n#)", r"\n\n## Chapter \1: \2", story
        )

        # Fix scene transitions if they exist but aren't formatted
        story = re.sub(r"(?<!\n\n)Scene (\d+)(?!\n#)", r"\n\n### Scene \1", story)

        # Save to file with robust error handling
        try:
            # Ensure the directory exists
            output_dir = os.path.dirname(args.output)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)

            # Write the file with error handling
            with open(args.output, "w") as f:
                f.write(story)
            print(f"Story successfully saved to {args.output}")

            # Database persistence is automatic for the single story

            # Always generate info file
            if "state" in locals():
                try:
                    info_file = save_story_info(state, args.output)
                    print(f"Story information saved to {info_file}")
                except Exception as info_err:
                    print(f"Error saving story information: {str(info_err)}")
        except OSError as e:
            print(f"Error saving story to {args.output}: {str(e)}")
            # Try to save to a fallback location
            fallback_path = "story_fallback.md"
            try:
                with open(fallback_path, "w") as f:
                    f.write(story)
                print(f"Story saved to fallback location: {fallback_path}")

                # Try to save info file for fallback too
                if "state" in locals():
                    try:
                        info_file = save_story_info(state, fallback_path)
                        print(f"Story information saved to {info_file}")
                    except Exception as info_err:
                        print(f"Error saving story information: {str(info_err)}")
            except OSError as fallback_err:
                print(
                    f"Critical error: Could not save story to fallback location: {str(fallback_err)}"
                )

        # Calculate total elapsed time
        elapsed_time = time.time() - start_time
        elapsed_str = f"{int(elapsed_time // 60)}m {int(elapsed_time % 60)}s"

        # Print summary statistics
        print("\nStory Generation Summary:")
        print(f"- Total time: {elapsed_str}")

        # Count chapters and scenes
        try:
            if "chapters" in story:
                chapter_count = 0
                scene_count = 0

                # Roughly count chapters and scenes from the markdown
                chapter_lines = [
                    line for line in story.split("\n") if line.startswith("## Chapter")
                ]
                scene_lines = [
                    line for line in story.split("\n") if line.startswith("### Scene")
                ]

                chapter_count = len(chapter_lines)
                scene_count = len(scene_lines)

                if chapter_count > 0:
                    print(f"- Chapters: {chapter_count}")
                if scene_count > 0:
                    print(f"- Scenes: {scene_count}")
        except:
            pass

        # Word count statistics
        word_count = len(story.split())
        print(f"- Word count: {word_count}")

        print(f"\nStory successfully saved to {args.output} in markdown format")

        # Generate audiobook SSML if requested during generation
        if args.audio_book:
            try:
                print("\nGenerating SSML for audiobook...")
                from storyteller_lib.audiobook.ssml.converter import SSMLConverter

                # Create SSML converter with the appropriate configuration
                ssml_converter = SSMLConverter(
                    model_provider=args.model_provider,
                    model=args.model,
                    language=args.language,
                )

                # Generate output filename for SSML
                base_name = os.path.splitext(args.output)[0]
                ssml_output = f"{base_name}_audiobook.ssml"

                # Convert the book to SSML
                ssml_converter.convert_book_to_ssml(DATABASE_PATH, ssml_output)

                print(f"SSML audiobook successfully saved to {ssml_output}")
                print("\nTo generate audio files, run:")
                print("  nix develop -c python generate_audiobook.py")

            except Exception as ssml_err:
                print(f"Error generating audiobook SSML: {str(ssml_err)}")
                import traceback

                traceback.print_exc()

    except Exception as e:
        print(f"Error during story generation: {str(e)}")
        import traceback

        traceback.print_exc()
        print("Please check the error message above and fix the issue in the code.")


if __name__ == "__main__":
    main()
