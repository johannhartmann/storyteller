"""
SSML Converter Module

This module provides functionality to convert story scenes and complete books
to SSML (Speech Synthesis Markup Language) format for audiobook generation.
"""

from typing import Dict
from jinja2 import Environment, FileSystemLoader, select_autoescape
import os
import xml.etree.ElementTree as ET

from storyteller_lib.core.config import get_llm
from storyteller_lib.core.logger import get_logger
from storyteller_lib.persistence.models.models import StoryDatabase

logger = get_logger(__name__)


class SSMLConverter:
    """Converts story content to SSML format for audiobook generation."""

    def __init__(
        self, model_provider: str = None, model: str = None, language: str = "english"
    ):
        """
        Initialize the SSML converter.

        Args:
            model_provider: The LLM provider to use
            model: The specific model to use
            language: The language for templates ("english" or "german")
        """
        self.language = language
        self.llm = get_llm(provider=model_provider, model=model)

        # Setup Jinja2 environment
        # Get the base directory of the storyteller_lib package
        import storyteller_lib

        package_dir = os.path.dirname(storyteller_lib.__file__)
        template_dir = os.path.join(package_dir, "prompts", "templates")

        # Determine template path based on language
        if language == "german":
            template_path = os.path.join(template_dir, "languages", "german")
        else:
            template_path = os.path.join(template_dir, "base")

        self.env = Environment(
            loader=FileSystemLoader(
                [template_path, os.path.join(template_dir, "base")]
            ),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def scene_to_ssml(
        self,
        scene_content: str,
        chapter_number: int,
        scene_number: int,
        scene_description: str,
        genre: str,
        tone: str,
        chapter_title: str = None,
        book_title: str = None,
        is_first_scene_in_chapter: bool = False,
        is_first_scene_in_book: bool = False,
    ) -> str:
        """
        Convert a single scene to SSML format.

        Args:
            scene_content: The scene text content
            chapter_number: Chapter number
            scene_number: Scene number within the chapter
            scene_description: Brief description of the scene
            genre: Story genre
            tone: Story tone
            chapter_title: Title of the current chapter
            book_title: Title of the book (for first scene)
            is_first_scene_in_chapter: Whether this is the first scene in the chapter
            is_first_scene_in_book: Whether this is the first scene in the book

        Returns:
            SSML-formatted scene content
        """
        try:
            # Load the template
            template = self.env.get_template("scene_to_ssml.jinja2")

            # Render the prompt
            prompt = template.render(
                scene_content=scene_content,
                chapter_number=chapter_number,
                scene_number=scene_number,
                scene_description=scene_description,
                genre=genre,
                tone=tone,
                chapter_title=chapter_title,
                book_title=book_title,
                is_first_scene_in_chapter=is_first_scene_in_chapter,
                is_first_scene_in_book=is_first_scene_in_book,
            )

            # Generate SSML using LLM
            response = self.llm.invoke(prompt)

            if hasattr(response, "content"):
                ssml_content = response.content
            else:
                ssml_content = str(response)

            # Fix smart quotes to prevent XML parsing errors
            ssml_content = self._fix_smart_quotes(ssml_content)

            # Basic validation - ensure it starts with <speak> and ends with </speak>
            ssml_content = ssml_content.strip()
            if not ssml_content.startswith("<speak"):
                logger.warning("SSML output missing <speak> tag, adding it")
                ssml_content = f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{self._get_lang_code()}">\n{ssml_content}\n</speak>'
            else:
                # Ensure existing <speak> tag has language attribute
                if "xml:lang" not in ssml_content:
                    logger.info("Adding language attribute to <speak> tag")
                    ssml_content = ssml_content.replace(
                        "<speak>",
                        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{self._get_lang_code()}">',
                    )

            if not ssml_content.endswith("</speak>"):
                logger.warning("SSML output missing closing </speak> tag, adding it")
                ssml_content = ssml_content + "\n</speak>"

            # Validate the final SSML
            if not self._validate_ssml(ssml_content):
                logger.warning("Generated SSML failed validation, using fallback")
                return self._create_fallback_ssml(scene_content)

            return ssml_content

        except Exception as e:
            logger.error(f"Error converting scene to SSML: {str(e)}")
            # Return a basic SSML wrapper as fallback
            return self._create_fallback_ssml(scene_content)

    def _get_lang_code(self) -> str:
        """Get the appropriate language code for SSML."""
        if self.language == "german":
            return "de-DE"
        else:
            return "en-US"

    def _get_voice_name(self) -> str:
        """Get the appropriate voice name for the language."""
        if self.language == "german":
            return "de-DE-SeraphinaMultilingualNeural"
        else:
            return "en-US-JennyNeural"

    def _create_fallback_ssml(self, content: str) -> str:
        """Create a basic SSML wrapper as fallback."""
        # Fix smart quotes in fallback content too
        content = self._fix_smart_quotes(content)
        return f"""<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{self._get_lang_code()}">
    <voice name="{self._get_voice_name()}">
        {content}
    </voice>
</speak>"""

    def _fix_smart_quotes(self, text: str) -> str:
        """Replace smart quotes with straight quotes to prevent XML parsing errors."""
        # Define replacements using Unicode escapes to avoid syntax issues
        replacements = {
            "\u201C": '"',  # Left double quotation mark
            "\u201D": '"',  # Right double quotation mark
            "\u201E": '"',  # Double low-9 quotation mark (German)
            "\u201F": '"',  # Double high-reversed-9 quotation mark
            "\u2018": "'",  # Left single quotation mark
            "\u2019": "'",  # Right single quotation mark
            "\u201A": "'",  # Single low-9 quotation mark
            "\u201B": "'",  # Single high-reversed-9 quotation mark
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        return text

    def _validate_ssml(self, ssml_content: str) -> bool:
        """Validate that the SSML is well-formed XML and follows Azure TTS rules."""
        try:
            # Parse the XML to check if it's valid
            root = ET.fromstring(ssml_content)

            # Additional validation: check root element
            tag_name = root.tag.split("}")[-1] if "}" in root.tag else root.tag
            if tag_name != "speak":
                logger.error(f"SSML root element is <{tag_name}>, not <speak>")
                return False

            # Azure TTS specific validation
            if not self._validate_azure_rules(root):
                return False

            return True
        except ET.ParseError as e:
            logger.error(f"SSML XML validation failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error validating SSML: {e}")
            return False

    def _validate_azure_rules(self, root: ET.Element) -> bool:
        """Validate Azure TTS specific rules."""
        # Check for text directly in speak tag
        if root.text and root.text.strip():
            logger.error("Found text directly in <speak> tag - must be inside <voice>")
            return False

        # Check for break tags directly in speak
        for child in root:
            tag_name = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag_name == "break":
                logger.error(
                    "Found <break> directly in <speak> - must be inside <voice>"
                )
                return False

        # Check for nested voice tags and prosody/voice nesting
        voice_elements = root.findall(".//{*}voice")
        for voice in voice_elements:
            # Check for voice inside voice
            nested_voices = voice.findall(".//{*}voice")
            if nested_voices:
                logger.error("Found nested <voice> tags - not allowed")
                return False

        # Check for voice inside prosody
        prosody_elements = root.findall(".//{*}prosody")
        for prosody in prosody_elements:
            voices_in_prosody = prosody.findall(".//{*}voice")
            if voices_in_prosody:
                logger.error(
                    "Found <voice> inside <prosody> - must be other way around"
                )
                return False

        return True

    def convert_book_to_ssml(self, db_path: str, output_path: str) -> None:
        """
        Convert the entire book to SSML format and save to file.

        Args:
            db_path: Path to the story database
            output_path: Path where the SSML book should be saved
        """
        try:
            logger.info("Starting full book SSML conversion")

            # Initialize database
            db = StoryDatabase(db_path)

            # Get story metadata
            story_config = db.get_story_config()
            genre = story_config.get("genre", "fiction")
            tone = story_config.get("tone", "neutral")
            title = story_config.get("title", "Untitled Story")

            # Start building the SSML book
            ssml_parts = []
            ssml_parts.append(
                f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{self._get_lang_code()}">'
            )
            ssml_parts.append(f'<voice name="{self._get_voice_name()}">')

            # Add title with dramatic pause
            ssml_parts.append(f'<emphasis level="strong">{title}</emphasis>')
            ssml_parts.append('<break time="2000ms"/>')

            # Get all chapters and scenes
            with db._get_connection() as conn:
                cursor = conn.cursor()

                # First, get total count for progress tracking
                cursor.execute(
                    """
                    SELECT COUNT(*) as total_scenes
                    FROM scenes s
                    JOIN chapters c ON s.chapter_id = c.id
                    WHERE s.content IS NOT NULL
                """
                )
                total_scenes = cursor.fetchone()["total_scenes"]

                print(f"Converting {total_scenes} scenes to SSML format...")
                print("This may take several minutes depending on the story length.\n")

                cursor.execute(
                    """
                    SELECT c.chapter_number, c.title as chapter_title, 
                        s.scene_number, s.content, s.description, s.id as scene_id
                    FROM chapters c
                    LEFT JOIN scenes s ON s.chapter_id = c.id
                    WHERE s.content IS NOT NULL
                    ORDER BY c.chapter_number, s.scene_number
                """
                )

                current_chapter = None
                scene_count = 0

                for row in cursor.fetchall():
                    # Add chapter header if new chapter
                    if row["chapter_number"] != current_chapter:
                        current_chapter = row["chapter_number"]
                        if current_chapter > 1:
                            # Add longer pause between chapters
                            ssml_parts.append('<break time="3000ms"/>')
                        ssml_parts.append(
                            f'<emphasis level="moderate">Chapter {current_chapter}: {row["chapter_title"]}</emphasis>'
                        )
                        ssml_parts.append('<break time="1500ms"/>')

                    # Update progress
                    scene_count += 1
                    print(
                        f"Converting scene {scene_count}/{total_scenes}: Chapter {row['chapter_number']}, Scene {row['scene_number']}...",
                        end="",
                        flush=True,
                    )

                    # Determine if this is the first scene in chapter/book
                    is_first_scene_in_chapter = row["scene_number"] == 1
                    is_first_scene_in_book = (
                        row["chapter_number"] == 1 and row["scene_number"] == 1
                    )

                    # Convert scene to SSML
                    scene_ssml = self.scene_to_ssml(
                        scene_content=row["content"],
                        chapter_number=row["chapter_number"],
                        scene_number=row["scene_number"],
                        scene_description=row["description"] or "",
                        genre=genre,
                        tone=tone,
                        chapter_title=row["chapter_title"],
                        book_title=title if is_first_scene_in_book else None,
                        is_first_scene_in_chapter=is_first_scene_in_chapter,
                        is_first_scene_in_book=is_first_scene_in_book,
                    )

                    print(" ✓")

                    # Extract just the content between <speak> tags to avoid nesting
                    if "<speak" in scene_ssml and "</speak>" in scene_ssml:
                        start = scene_ssml.find(">") + 1
                        end = scene_ssml.rfind("</speak>")
                        scene_content = scene_ssml[start:end]

                        # Also remove any nested voice tags
                        if "<voice" in scene_content:
                            voice_start = scene_content.find("<voice")
                            voice_tag_end = scene_content.find(">", voice_start) + 1
                            scene_content = scene_content[voice_tag_end:]
                            voice_end = scene_content.rfind("</voice>")
                            if voice_end > 0:
                                scene_content = scene_content[:voice_end]
                    else:
                        scene_content = scene_ssml

                    ssml_parts.append(scene_content)

                    # Update database with SSML content (already has smart quotes fixed)
                    db.update_scene_ssml(row["scene_id"], scene_ssml)

                    # Add pause between scenes
                    ssml_parts.append('<break time="1500ms"/>')

            # Close SSML document
            ssml_parts.append("</voice>")
            ssml_parts.append("</speak>")

            # Write the complete SSML book
            full_ssml = "\n".join(ssml_parts)

            print(f"\nWriting SSML audiobook to {output_path}...")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(full_ssml)

            print(f"✓ SSML conversion complete! All {scene_count} scenes processed.")
            logger.info(f"SSML book successfully saved to {output_path}")

        except Exception as e:
            logger.error(f"Error converting book to SSML: {str(e)}")
            raise
