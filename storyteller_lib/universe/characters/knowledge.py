"""
Character Knowledge Manager - Unified API for character knowledge tracking.

This module provides a centralized interface for managing what characters know,
their secrets, and knowledge revelations throughout the story.
"""

from typing import List, Dict, Any, Optional, Literal
from storyteller_lib.core.logger import get_logger
from storyteller_lib.persistence.database import get_db_manager

logger = get_logger(__name__)

KnowledgeVisibility = Literal["public", "secret", "revealed"]


class CharacterKnowledgeManager:
    """Unified manager for character knowledge tracking."""

    def __init__(self):
        """Initialize the knowledge manager."""
        self.db_manager = get_db_manager()
        if not self.db_manager or not self.db_manager._db:
            raise RuntimeError("Database manager not available")

    def add_knowledge(
        self,
        character_id: int,
        knowledge: str,
        scene_id: int,
        knowledge_type: str = "fact",
        visibility: KnowledgeVisibility = "public",
        source: Optional[str] = None,
    ) -> bool:
        """
        Add new knowledge for a character.

        Args:
            character_id: Database ID of the character
            knowledge: The knowledge content
            scene_id: Scene where knowledge was gained
            knowledge_type: Type of knowledge (fact, secret, rumor, etc.)
            visibility: Knowledge visibility level
            source: How the character learned this

        Returns:
            True if successfully added, False otherwise
        """
        try:
            with self.db_manager._db._get_connection() as conn:
                cursor = conn.cursor()

                # Check if this knowledge already exists
                cursor.execute(
                    """
                    SELECT id FROM character_knowledge 
                    WHERE character_id = ? AND knowledge_content = ?
                """,
                    (character_id, knowledge),
                )

                if cursor.fetchone():
                    logger.warning(
                        f"Knowledge already exists for character {character_id}: {knowledge}"
                    )
                    return False

                # Add the knowledge
                cursor.execute(
                    """
                    INSERT INTO character_knowledge 
                    (character_id, scene_id, knowledge_type, knowledge_content, source)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        character_id,
                        scene_id,
                        f"{knowledge_type}:{visibility}",  # Encode visibility in type
                        knowledge,
                        source or f"Learned in scene {scene_id}",
                    ),
                )
                conn.commit()

                logger.info(
                    f"Added {visibility} knowledge for character {character_id}: {knowledge}"
                )
                return True

        except Exception as e:
            logger.error(f"Failed to add knowledge: {e}")
            return False

    def get_character_knowledge(
        self,
        character_id: int,
        scene_id: Optional[int] = None,
        visibility: Optional[KnowledgeVisibility] = None,
        knowledge_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all knowledge for a character.

        Args:
            character_id: Database ID of the character
            scene_id: If provided, only get knowledge up to this scene
            visibility: Filter by visibility level
            knowledge_type: Filter by knowledge type

        Returns:
            List of knowledge entries
        """
        try:
            with self.db_manager._db._get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT ck.*, s.scene_number, c.chapter_number
                    FROM character_knowledge ck
                    JOIN scenes s ON ck.scene_id = s.id
                    JOIN chapters c ON s.chapter_id = c.id
                    WHERE ck.character_id = ?
                """
                params = [character_id]

                if scene_id:
                    query += " AND ck.scene_id <= ?"
                    params.append(scene_id)

                if visibility:
                    query += " AND ck.knowledge_type LIKE ?"
                    params.append(f"%:{visibility}")

                if knowledge_type:
                    query += " AND ck.knowledge_type LIKE ?"
                    params.append(f"{knowledge_type}:%")

                query += " ORDER BY c.chapter_number, s.scene_number"

                cursor.execute(query, params)

                knowledge = []
                for row in cursor.fetchall():
                    # Parse visibility from knowledge_type
                    type_parts = row["knowledge_type"].split(":", 1)
                    k_type = type_parts[0]
                    k_visibility = type_parts[1] if len(type_parts) > 1 else "public"

                    knowledge.append(
                        {
                            "id": row["id"],
                            "content": row["knowledge_content"],
                            "type": k_type,
                            "visibility": k_visibility,
                            "source": row["source"],
                            "chapter": row["chapter_number"],
                            "scene": row["scene_number"],
                        }
                    )

                return knowledge

        except Exception as e:
            logger.error(f"Failed to get character knowledge: {e}")
            return []

    def reveal_secret(
        self,
        character_id: int,
        secret_content: str,
        scene_id: int,
        reveal_to: Optional[List[int]] = None,
    ) -> bool:
        """
        Reveal a character's secret.

        Args:
            character_id: Character whose secret is being revealed
            secret_content: The secret being revealed
            scene_id: Scene where secret is revealed
            reveal_to: List of character IDs who learn the secret

        Returns:
            True if successfully revealed, False otherwise
        """
        try:
            with self.db_manager._db._get_connection() as conn:
                cursor = conn.cursor()

                # Find the secret
                cursor.execute(
                    """
                    SELECT id FROM character_knowledge
                    WHERE character_id = ? 
                    AND knowledge_content = ?
                    AND knowledge_type LIKE '%:secret'
                """,
                    (character_id, secret_content),
                )

                secret = cursor.fetchone()
                if not secret:
                    logger.warning(
                        f"Secret not found for character {character_id}: {secret_content}"
                    )
                    return False

                # Update secret visibility to revealed
                cursor.execute(
                    """
                    UPDATE character_knowledge
                    SET knowledge_type = REPLACE(knowledge_type, ':secret', ':revealed')
                    WHERE id = ?
                """,
                    (secret["id"],),
                )

                # Add knowledge to characters who learn it
                if reveal_to:
                    for learner_id in reveal_to:
                        if learner_id != character_id:  # Don't add to self
                            cursor.execute(
                                """
                                INSERT INTO character_knowledge
                                (character_id, scene_id, knowledge_type, knowledge_content, source)
                                VALUES (?, ?, ?, ?, ?)
                            """,
                                (
                                    learner_id,
                                    scene_id,
                                    "learned_secret:public",
                                    secret_content,
                                    f"Revealed by character {character_id}",
                                ),
                            )

                conn.commit()
                logger.info(
                    f"Revealed secret for character {character_id}: {secret_content}"
                )
                return True

        except Exception as e:
            logger.error(f"Failed to reveal secret: {e}")
            return False

    def check_knowledge_exists(
        self, character_id: int, knowledge: str, exact_match: bool = True
    ) -> bool:
        """
        Check if a character already has specific knowledge.

        Args:
            character_id: Database ID of the character
            knowledge: The knowledge to check for
            exact_match: If True, check exact match; if False, check substring

        Returns:
            True if character has this knowledge, False otherwise
        """
        try:
            with self.db_manager._db._get_connection() as conn:
                cursor = conn.cursor()

                if exact_match:
                    cursor.execute(
                        """
                        SELECT id FROM character_knowledge
                        WHERE character_id = ? AND knowledge_content = ?
                    """,
                        (character_id, knowledge),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT id FROM character_knowledge
                        WHERE character_id = ? AND knowledge_content LIKE ?
                    """,
                        (character_id, f"%{knowledge}%"),
                    )

                return cursor.fetchone() is not None

        except Exception as e:
            logger.error(f"Failed to check knowledge existence: {e}")
            return False

    def get_character_secrets(
        self, character_id: int, include_revealed: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all secrets for a character.

        Args:
            character_id: Database ID of the character
            include_revealed: If True, include revealed secrets

        Returns:
            List of secret entries
        """
        visibility_filter = ["secret"]
        if include_revealed:
            visibility_filter.append("revealed")

        secrets = []
        for vis in visibility_filter:
            secrets.extend(
                self.get_character_knowledge(
                    character_id, visibility=vis, knowledge_type="secret"
                )
            )

        return secrets

    def get_character_id_by_name(self, character_name: str) -> Optional[int]:
        """
        Helper to get character database ID by name or identifier.

        Args:
            character_name: Character name or identifier

        Returns:
            Character database ID or None if not found
        """
        try:
            with self.db_manager._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id FROM characters 
                    WHERE identifier = ? OR name = ?
                """,
                    (character_name, character_name),
                )

                result = cursor.fetchone()
                return result["id"] if result else None

        except Exception as e:
            logger.error(f"Failed to get character ID: {e}")
            return None
