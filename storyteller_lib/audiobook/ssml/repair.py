"""
SSML Repair Module

This module provides functionality to repair SSML content based on Azure TTS error messages.
It uses LLM to intelligently fix common SSML errors and validates the repaired content.
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from storyteller_lib.core.config import get_llm
from storyteller_lib.core.logger import get_logger
from storyteller_lib.persistence.models.models import StoryDatabase

logger = get_logger(__name__)


@dataclass
class AzureError:
    """Parsed Azure TTS error information."""

    code: int
    message: str
    details: str | None = None


class SSMLRepair:
    """Repairs SSML content based on Azure TTS error messages."""

    # Known Azure TTS error patterns and their repair strategies
    ERROR_PATTERNS = {
        1007: {
            "pattern": r"Node \[(\w+)\] with type \[(\w+)\] should not contain node \[(\w+)\] with type \[(\w+)\]|Unsupported voice|node can only contain Element or Comment",
            "description": "Invalid SSML nesting or unsupported elements",
            "repair_strategy": "fix_invalid_nesting",
        },
        1001: {
            "pattern": r"Invalid SSML syntax",
            "description": "General SSML syntax error",
            "repair_strategy": "fix_syntax_error",
        },
        1002: {
            "pattern": r"Invalid attribute value",
            "description": "Invalid attribute value",
            "repair_strategy": "fix_attribute_values",
        },
        1003: {
            "pattern": r"Unsupported element",
            "description": "Unsupported SSML element",
            "repair_strategy": "remove_unsupported_elements",
        },
        1004: {
            "pattern": r"Invalid prosody",
            "description": "Invalid prosody values",
            "repair_strategy": "fix_prosody_values",
        },
    }

    def __init__(self, db_path: str, model_provider: str = None, model: str = None):
        """
        Initialize the SSML repair module.

        Args:
            db_path: Path to the story database
            model_provider: LLM provider to use
            model: Specific model to use
        """
        self.db = StoryDatabase(db_path)
        self.llm = get_llm(provider=model_provider, model=model)

    def parse_azure_error(self, error_message: str) -> AzureError:
        """
        Parse Azure TTS error message.

        Args:
            error_message: Error message from Azure TTS

        Returns:
            Parsed error information
        """
        # Pattern: "Error code: 1007. Error details: Node [prosody] with type [Others] should not contain node [voice] with type [Media]."
        code_match = re.search(r"Error code:\s*(\d+)", error_message)
        details_match = re.search(r"Error details:\s*(.+)", error_message)

        error_code = int(code_match.group(1)) if code_match else 0
        error_details = details_match.group(1) if details_match else error_message

        return AzureError(code=error_code, message=error_message, details=error_details)

    def repair_ssml(
        self, scene_id: int, original_ssml: str, error_message: str, attempt: int = 1
    ) -> str | None:
        """
        Repair SSML content based on error message.

        Args:
            scene_id: Database scene ID
            original_ssml: Original SSML content
            error_message: Azure TTS error message
            attempt: Repair attempt number (1-3)

        Returns:
            Repaired SSML or None if repair failed
        """
        try:
            # Parse error
            error = self.parse_azure_error(error_message)
            logger.info(
                f"Repairing SSML for scene {scene_id}, error code: {error.code}, attempt: {attempt}"
            )

            # Try specific repair strategy first
            if error.code in self.ERROR_PATTERNS:
                strategy = self.ERROR_PATTERNS[error.code]["repair_strategy"]
                repaired_ssml = self._apply_repair_strategy(
                    original_ssml, error, strategy, attempt
                )
            else:
                # Use general LLM repair for unknown errors
                repaired_ssml = self._repair_with_llm(original_ssml, error, attempt)

            # Validate repaired SSML
            if repaired_ssml and self._validate_ssml(repaired_ssml):
                # Log repair attempt
                self._log_repair_attempt(
                    scene_id=scene_id,
                    error_code=error.code,
                    error_message=error_message,
                    repair_attempt=attempt,
                    original_ssml=original_ssml,
                    repaired_ssml=repaired_ssml,
                    successful=True,
                )
                return repaired_ssml
            else:
                logger.warning(f"Repaired SSML failed validation for scene {scene_id}")
                self._log_repair_attempt(
                    scene_id=scene_id,
                    error_code=error.code,
                    error_message=error_message,
                    repair_attempt=attempt,
                    original_ssml=original_ssml,
                    repaired_ssml=repaired_ssml or "",
                    successful=False,
                )
                return None

        except Exception as e:
            logger.error(f"Error repairing SSML for scene {scene_id}: {str(e)}")
            return None

    def _apply_repair_strategy(
        self, ssml: str, error: AzureError, strategy: str, attempt: int
    ) -> str | None:
        """Apply specific repair strategy based on error type."""
        if strategy == "fix_invalid_nesting":
            return self._fix_invalid_nesting(ssml, error, attempt)
        elif strategy == "fix_syntax_error":
            return self._fix_syntax_error(ssml, error, attempt)
        elif strategy == "fix_attribute_values":
            return self._fix_attribute_values(ssml, error, attempt)
        elif strategy == "fix_prosody_values":
            return self._fix_prosody_values(ssml, error, attempt)
        elif strategy == "remove_unsupported_elements":
            return self._remove_unsupported_elements(ssml, error, attempt)
        else:
            # Fallback to LLM repair
            return self._repair_with_llm(ssml, error, attempt)

    def _fix_invalid_nesting(
        self, ssml: str, error: AzureError, attempt: int
    ) -> str | None:
        """Fix invalid SSML nesting and structure errors."""
        error_details = error.details.lower() if error.details else ""

        # Determine specific error type
        if "prosody" in error_details and "voice" in error_details:
            fix_type = "prosody_voice_nesting"
        elif (
            "voice" in error_details
            and "should not contain node [voice]" in error_details
        ):
            fix_type = "nested_voice"
        elif "speak" in error_details and "break" in error_details:
            fix_type = "break_in_speak"
        elif "unsupported voice" in error_details:
            fix_type = "unsupported_voice"
        elif "can only contain element or comment" in error_details:
            fix_type = "text_in_speak"
        else:
            fix_type = "general"

        prompt = f"""Fix the following SSML based on this Azure TTS error: {error.details}

Original SSML:
{ssml}

CRITICAL RULES FOR AZURE TTS:
1. Structure must be: <speak><voice>ALL CONTENT HERE</voice></speak>
2. NO nested <voice> tags - only ONE voice tag wrapping all content
3. <prosody> tags must be INSIDE <voice>, never the other way around
4. <break> tags must be INSIDE <voice>, never directly in <speak>
5. ALL text must be inside <voice> tags - no bare text in <speak>
6. Valid German voices: de-DE-ConradNeural, de-DE-KatjaNeural, de-DE-AmalaNeural, de-DE-SeraphinaMultilingualNeural
7. Valid English voices: en-US-JennyNeural, en-US-AriaNeural, en-US-GuyNeural, en-US-AvaMultilingualNeural

Specific fix needed: {fix_type}
"""

        if fix_type == "prosody_voice_nesting":
            prompt += """
The error shows <voice> inside <prosody>. Restructure so <prosody> is inside <voice>."""
        elif fix_type == "nested_voice":
            prompt += """
The error shows nested <voice> tags. Use only ONE <voice> tag wrapping all content."""
        elif fix_type == "break_in_speak":
            prompt += """
The error shows <break> directly in <speak>. Move ALL <break> tags inside the <voice> tag."""
        elif fix_type == "unsupported_voice":
            prompt += """
The voice name is not supported. Replace with a valid voice from the list above based on language."""
        elif fix_type == "text_in_speak":
            prompt += """
There is text directly in <speak>. ALL text must be inside <voice> tags."""

        prompt += """

Return ONLY the fixed SSML without any explanation.

Fixed SSML:"""

        response = self.llm.invoke(prompt)
        return response.content if hasattr(response, "content") else str(response)

    def _fix_syntax_error(
        self, ssml: str, error: AzureError, attempt: int
    ) -> str | None:
        """Fix general SSML syntax errors."""
        prompt = f"""Fix the following SSML that has a syntax error. Azure TTS error: {error.details}

Original SSML:
{ssml}

Common syntax issues to check:
1. Unclosed tags
2. Mismatched tags
3. Invalid XML characters (& < > " ')
4. Missing required attributes
5. Improper namespaces

Return only the fixed SSML without any explanation.

Fixed SSML:"""

        response = self.llm.invoke(prompt)
        return response.content if hasattr(response, "content") else str(response)

    def _fix_attribute_values(
        self, ssml: str, error: AzureError, attempt: int
    ) -> str | None:
        """Fix invalid attribute values in SSML."""
        prompt = f"""Fix the following SSML that has invalid attribute values. Azure TTS error: {error.details}

Original SSML:
{ssml}

Common attribute value issues:
1. Rate values must be: x-slow, slow, medium, fast, x-fast, or a percentage (e.g., "80%")
2. Pitch values must be: x-low, low, medium, high, x-high, or a relative change (e.g., "+2st", "-5Hz")
3. Volume values must be: silent, x-soft, soft, medium, loud, x-loud, or a number (0-100)
4. Break time must be in milliseconds (e.g., "500ms") or seconds (e.g., "1.5s")

Return only the fixed SSML without any explanation.

Fixed SSML:"""

        response = self.llm.invoke(prompt)
        return response.content if hasattr(response, "content") else str(response)

    def _fix_prosody_values(
        self, ssml: str, error: AzureError, attempt: int
    ) -> str | None:
        """Fix invalid prosody values specifically."""
        prompt = f"""Fix the following SSML that has invalid prosody values. Azure TTS error: {error.details}

Original SSML:
{ssml}

Valid prosody attributes and values:
- rate: x-slow, slow, medium, fast, x-fast, or percentage (50%-200%)
- pitch: x-low, low, medium, high, x-high, or relative (+/-Hz or +/-st)
- volume: silent, x-soft, soft, medium, loud, x-loud, or 0-100
- contour: pitch changes over time (advanced feature)

Common issues:
1. Using "very slow" instead of "x-slow"
2. Using invalid percentages (e.g., "250%")
3. Missing units for relative values

Return only the fixed SSML without any explanation.

Fixed SSML:"""

        response = self.llm.invoke(prompt)
        return response.content if hasattr(response, "content") else str(response)

    def _remove_unsupported_elements(
        self, ssml: str, error: AzureError, attempt: int
    ) -> str | None:
        """Remove unsupported SSML elements."""
        prompt = f"""Fix the following SSML by removing unsupported elements. Azure TTS error: {error.details}

Original SSML:
{ssml}

Azure TTS supports these SSML elements:
- speak, voice, prosody, break, emphasis, say-as, phoneme, sub
- audio (for inserting audio files)
- mstts:express-as (for Azure Neural voices)
- mstts:silence (for precise silence control)

Remove any unsupported elements while preserving the content inside them.

Return only the fixed SSML without any explanation.

Fixed SSML:"""

        response = self.llm.invoke(prompt)
        return response.content if hasattr(response, "content") else str(response)

    def _repair_with_llm(
        self, ssml: str, error: AzureError, attempt: int
    ) -> str | None:
        """General LLM-based SSML repair."""
        # More aggressive prompt for subsequent attempts
        aggressiveness = ["conservative", "moderate", "aggressive"][min(attempt - 1, 2)]

        prompt = f"""Repair the following SSML content that Azure TTS rejected. This is attempt {attempt}/3.

Azure TTS Error: {error.message}

Original SSML:
{ssml}

Repair approach: {aggressiveness}
{"- Conservative: Fix only the specific error mentioned" if attempt == 1 else ""}
{"- Moderate: Fix the error and check for related issues" if attempt == 2 else ""}
{"- Aggressive: Simplify the SSML structure while preserving speech effects" if attempt == 3 else ""}

Important rules:
1. The repaired SSML must be valid XML
2. All tags must be properly closed
3. Use only Azure TTS supported elements
4. Preserve the original content and intent
5. Fix smart quotes and special characters

Return only the repaired SSML without any explanation.

Repaired SSML:"""

        response = self.llm.invoke(prompt)
        return response.content if hasattr(response, "content") else str(response)

    def _validate_ssml(self, ssml: str) -> bool:
        """Validate that the SSML is well-formed XML."""
        try:
            # Parse the XML to check if it's valid
            root = ET.fromstring(ssml)

            # Check root element
            tag_name = root.tag.split("}")[-1] if "}" in root.tag else root.tag
            if tag_name != "speak":
                logger.error(f"SSML root element is <{tag_name}>, not <speak>")
                return False

            # Check for required attributes
            if "version" not in root.attrib:
                logger.warning("SSML missing version attribute")

            return True
        except ET.ParseError as e:
            logger.error(f"SSML XML validation failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error validating SSML: {e}")
            return False

    def _log_repair_attempt(
        self,
        scene_id: int,
        error_code: int,
        error_message: str,
        repair_attempt: int,
        original_ssml: str,
        repaired_ssml: str,
        successful: bool,
    ) -> None:
        """Log repair attempt to database."""
        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO ssml_repair_log
                    (scene_id, error_code, error_message, repair_attempt,
                     original_ssml, repaired_ssml, repair_successful)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        scene_id,
                        error_code,
                        error_message,
                        repair_attempt,
                        original_ssml,
                        repaired_ssml,
                        successful,
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log repair attempt: {str(e)}")

    def get_repair_history(self, scene_id: int) -> list:
        """Get repair history for a scene."""
        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM ssml_repair_log
                    WHERE scene_id = ?
                    ORDER BY created_at DESC
                """,
                    (scene_id,),
                )
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Failed to get repair history: {str(e)}")
            return []
