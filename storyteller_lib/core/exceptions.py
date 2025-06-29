"""Custom exception hierarchy for StoryCraft Agent.

This module defines custom exceptions for better error handling and debugging.
"""

# Standard library imports
from typing import Any, Dict, Optional


class StorytellerException(Exception):
    """Base exception for all StoryCraft Agent errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}


class ConfigurationError(StorytellerException):
    """Raised when there's an error in configuration.

    This exception is raised when configuration values are invalid,
    missing required settings, or when configuration files cannot be loaded.
    """

    pass


class LLMError(StorytellerException):
    """Base class for LLM-related errors.

    This is the base exception for all errors related to Language Model
    interactions, including connection issues, response errors, and quota limits.
    """

    pass


class LLMConnectionError(LLMError):
    """Raised when unable to connect to LLM provider.

    This exception indicates network issues, authentication failures,
    or unavailable LLM services.
    """

    pass


class LLMResponseError(LLMError):
    """Raised when LLM returns invalid or unexpected response.

    This exception is raised when the LLM response cannot be parsed,
    contains invalid data, or doesn't match expected format.
    """

    pass


class LLMQuotaError(LLMError):
    """Raised when LLM quota or rate limit is exceeded.

    This exception indicates that API rate limits have been hit
    or usage quotas have been exhausted.
    """

    pass


class MemoryError(StorytellerException):
    """Base class for memory system errors.

    This is the base exception for all errors related to the memory
    storage and retrieval system.
    """

    pass


class MemoryStorageError(MemoryError):
    """Raised when unable to store data in memory system.

    This exception indicates failures in persisting data to the
    memory store, including database errors or serialization issues.
    """

    pass


class MemoryRetrievalError(MemoryError):
    """Raised when unable to retrieve data from memory system.

    This exception indicates failures in fetching data from the
    memory store, including missing keys or deserialization errors.
    """

    pass


class StoryGenerationError(StorytellerException):
    """Base class for story generation errors.

    This is the base exception for all errors that occur during
    the story generation process.
    """

    pass


class SceneGenerationError(StoryGenerationError):
    """Raised when scene generation fails.

    Attributes:
        chapter: The chapter number where the error occurred.
        scene: The scene number where the error occurred.
    """

    def __init__(
        self,
        message: str,
        chapter: Optional[int] = None,
        scene: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details)
        self.chapter = chapter
        self.scene = scene


class CharacterCreationError(StoryGenerationError):
    """Raised when character creation fails.

    Attributes:
        character_name: The name of the character that failed to create.
    """

    def __init__(
        self,
        message: str,
        character_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details)
        self.character_name = character_name


class WorldBuildingError(StoryGenerationError):
    """Raised when world building fails.

    This exception is raised when the world building process encounters
    errors in creating settings, locations, or world elements.
    """

    pass


class PlotThreadError(StoryGenerationError):
    """Raised when plot thread management fails.

    Attributes:
        thread_name: The name of the plot thread that caused the error.
    """

    def __init__(
        self,
        message: str,
        thread_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details)
        self.thread_name = thread_name


class ValidationError(StorytellerException):
    """Base class for validation errors.

    This is the base exception for all validation-related errors,
    including language validation and quality checks.
    """

    pass


class LanguageValidationError(ValidationError):
    """Raised when language validation fails.

    Attributes:
        expected_language: The language the content should be in.
        detected_language: The language that was detected (if available).
    """

    def __init__(
        self,
        message: str,
        expected_language: str,
        detected_language: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details)
        self.expected_language = expected_language
        self.detected_language = detected_language


class QualityValidationError(ValidationError):
    """Raised when quality validation fails.

    Attributes:
        quality_scores: Dictionary of quality metrics and their scores.
        threshold: The threshold that was not met.
    """

    def __init__(
        self,
        message: str,
        quality_scores: Optional[Dict[str, float]] = None,
        threshold: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details)
        self.quality_scores = quality_scores
        self.threshold = threshold


class StateError(StorytellerException):
    """Base class for state management errors.

    This is the base exception for all errors related to story state
    management and state transitions.
    """

    pass


class InvalidStateError(StateError):
    """Raised when story state is invalid or corrupted.

    This exception indicates that the story state contains invalid data,
    missing required fields, or has become corrupted.
    """

    pass


class StateTransitionError(StateError):
    """Raised when invalid state transition is attempted.

    Attributes:
        from_node: The node attempting the transition.
        to_node: The target node of the transition.
    """

    def __init__(
        self,
        message: str,
        from_node: str,
        to_node: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details)
        self.from_node = from_node
        self.to_node = to_node


class FileOperationError(StorytellerException):
    """Base class for file operation errors.

    This is the base exception for all errors related to file
    input/output operations.
    """

    pass


class DatabaseError(StorytellerException):
    """Base class for database-related errors.

    This is the base exception for all errors related to database
    operations, including connection issues, query errors, and data integrity.
    """

    pass


class DatabaseConnectionError(DatabaseError):
    """Raised when unable to connect to database.

    This exception indicates database connection issues,
    including missing database files or permission errors.
    """

    pass


class DatabaseQueryError(DatabaseError):
    """Raised when database query fails.

    This exception indicates SQL query errors, including
    syntax errors or constraint violations.
    """

    pass


class DatabaseIntegrityError(DatabaseError):
    """Raised when database integrity is violated.

    This exception indicates data integrity issues,
    including foreign key violations or unique constraint failures.
    """

    pass


class OutputFileError(FileOperationError):
    """Raised when unable to write output file.

    Attributes:
        file_path: The path to the file that failed to write.
    """

    def __init__(
        self, message: str, file_path: str, details: Optional[Dict[str, Any]] = None
    ):
        """Initialize the output file error.

        Args:
               message: The error message.
           file_path: The path to the file that failed to write.
           details: Optional dictionary with additional error details.
        """
        super().__init__(message, details)
        self.file_path = file_path


class InputFileError(FileOperationError):
    """Raised when unable to read input file.

    Attributes:
        file_path: The path to the file that failed to read.
    """

    def __init__(
        self, message: str, file_path: str, details: Optional[Dict[str, Any]] = None
    ):
        """Initialize the input file error.

        Args:
               message: The error message.
           file_path: The path to the file that failed to read.
           details: Optional dictionary with additional error details.
        """
        super().__init__(message, details)
        self.file_path = file_path


# Utility functions for consistent error handling


def handle_llm_error(error: Exception, context: str = "") -> LLMError:
    """Convert generic exceptions to specific LLM errors.

    Args:
        error: The original exception
        context: Additional context about where the error occurred

    Returns:
        Appropriate LLMError subclass
    """
    error_msg = str(error)
    details = {"original_error": type(error).__name__, "context": context}

    if "rate limit" in error_msg.lower() or "quota" in error_msg.lower():
        return LLMQuotaError(f"LLM quota exceeded: {error_msg}", details)
    elif "connection" in error_msg.lower() or "timeout" in error_msg.lower():
        return LLMConnectionError(f"LLM connection failed: {error_msg}", details)
    else:
        return LLMResponseError(f"LLM error: {error_msg}", details)


def handle_memory_error(error: Exception, operation: str = "access") -> MemoryError:
    """Convert generic exceptions to specific memory errors.

    Args:
        error: The original exception
        operation: The operation that failed (store/retrieve/access)

    Returns:
        Appropriate MemoryError subclass
    """
    error_msg = str(error)
    details = {"original_error": type(error).__name__, "operation": operation}

    if operation == "store":
        return MemoryStorageError(f"Failed to store in memory: {error_msg}", details)
    elif operation == "retrieve":
        return MemoryRetrievalError(
            f"Failed to retrieve from memory: {error_msg}", details
        )
    else:
        return MemoryError(f"Memory operation failed: {error_msg}", details)
