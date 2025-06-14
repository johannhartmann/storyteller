"""Pydantic models for configuration validation.

This module provides validated configuration models for the StoryCraft Agent.
"""

# Standard library imports
from pathlib import Path
from typing import Any, Dict, Literal, Optional

# Third party imports
from pydantic import BaseModel, Field, root_validator, validator

# Local imports
from storyteller_lib.constants import (
    ConfigDefaults, STORY_LENGTHS, SUPPORTED_GENRES,
    SUPPORTED_LANGUAGES, SUPPORTED_TONES
)


class LLMConfig(BaseModel):
    """Configuration for Language Model settings."""
    
    provider: Literal["openai", "anthropic", "gemini"] = Field(
        default=ConfigDefaults.DEFAULT_MODEL_PROVIDER,
        description="LLM provider to use"
    )
    model: Optional[str] = Field(
        default=None,
        description="Specific model to use (defaults to provider's default)"
    )
    temperature: float = Field(
        default=ConfigDefaults.DEFAULT_TEMPERATURE,
        ge=0.0, le=2.0,
        description="Temperature for text generation"
    )
    max_tokens: int = Field(
        default=ConfigDefaults.DEFAULT_MAX_TOKENS,
        ge=100, le=128000,
        description="Maximum tokens for generation"
    )
    api_key: Optional[str] = Field(
        default=None,
        description="API key for the provider (loaded from environment if not provided)"
    )
    
    @validator("provider")
    def validate_provider(cls, v):
        """Validate that the provider is supported."""
        if v not in ["openai", "anthropic", "gemini"]:
            raise ValueError(f"Unsupported provider: {v}")
        return v
    
    class Config:
        """Pydantic configuration."""
        extra = "forbid"


class StoryConfig(BaseModel):
    """Configuration for story generation parameters."""
    
    genre: str = Field(
        default=ConfigDefaults.DEFAULT_GENRE,
        description="Story genre"
    )
    tone: str = Field(
        default=ConfigDefaults.DEFAULT_TONE,
        description="Story tone/mood"
    )
    language: str = Field(
        default=ConfigDefaults.DEFAULT_LANGUAGE,
        description="Language for story generation"
    )
    length: Literal["short", "medium", "long", "epic"] = Field(
        default=ConfigDefaults.DEFAULT_LENGTH,
        description="Story length preset"
    )
    chapters: Optional[int] = Field(
        default=None,
        ge=1, le=50,
        description="Number of chapters (overrides length preset)"
    )
    scenes_per_chapter: Optional[int] = Field(
        default=None,
        ge=1, le=20,
        description="Number of scenes per chapter (overrides length preset)"
    )
    author: Optional[str] = Field(
        default=None,
        description="Author style to emulate"
    )
    initial_idea: Optional[str] = Field(
        default=None,
        description="Initial story idea or premise"
    )
    
    @validator("genre")
    def validate_genre(cls, v):
        """Validate genre is supported."""
        if v.lower() not in [g.lower() for g in SUPPORTED_GENRES]:
            # Allow custom genres but warn
            import warnings
            warnings.warn(f"Using custom genre '{v}' - results may vary")
        return v
    
    @validator("tone")
    def validate_tone(cls, v):
        """Validate tone is supported."""
        if v.lower() not in [t.lower() for t in SUPPORTED_TONES]:
            # Allow custom tones but warn
            import warnings
            warnings.warn(f"Using custom tone '{v}' - results may vary")
        return v
    
    @validator("language")
    def validate_language(cls, v):
        """Validate language is supported."""
        if v.lower() not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported language: {v}. "
                f"Supported languages: {', '.join(SUPPORTED_LANGUAGES.keys())}"
            )
        return v.lower()
    
    @root_validator
    def set_chapter_scene_counts(cls, values):
        """Set chapter and scene counts based on length if not provided."""
        length = values.get("length")
        chapters = values.get("chapters")
        scenes_per_chapter = values.get("scenes_per_chapter")
        
        if chapters is None and length in STORY_LENGTHS:
            values["chapters"] = STORY_LENGTHS[length]["chapters"]
        
        if scenes_per_chapter is None and length in STORY_LENGTHS:
            values["scenes_per_chapter"] = STORY_LENGTHS[length]["scenes_per_chapter"]
            
        return values
    
    class Config:
        """Pydantic configuration."""
        extra = "forbid"


class CacheConfig(BaseModel):
    """Configuration for caching settings."""
    
    type: Literal["memory", "sqlite", "none"] = Field(
        default="sqlite",
        description="Type of cache to use"
    )
    path: Optional[Path] = Field(
        default=None,
        description="Path to cache file (for sqlite cache)"
    )
    
    @validator("path")
    def validate_cache_path(cls, v, values):
        """Validate cache path is valid for sqlite cache."""
        if values.get("type") == "sqlite" and v:
            # Ensure parent directory exists
            v.parent.mkdir(parents=True, exist_ok=True)
        return v
    
    class Config:
        """Pydantic configuration."""
        extra = "forbid"


class OutputConfig(BaseModel):
    """Configuration for output settings."""
    
    file_path: Path = Field(
        default=Path("story.md"),
        description="Output file path for the generated story"
    )
    format: Literal["markdown", "json", "html"] = Field(
        default="markdown",
        description="Output format"
    )
    save_info_file: bool = Field(
        default=False,
        description="Whether to save story metadata to a YAML file"
    )
    chapter_files: bool = Field(
        default=False,
        description="Whether to save each chapter as a separate file"
    )
    
    @validator("file_path")
    def validate_output_path(cls, v):
        """Ensure output directory exists."""
        v.parent.mkdir(parents=True, exist_ok=True)
        return v
    
    class Config:
        """Pydantic configuration."""
        extra = "forbid"


class LoggingConfig(BaseModel):
    """Configuration for logging settings."""
    
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level"
    )
    file_path: Optional[Path] = Field(
        default=None,
        description="Path to log file"
    )
    format: Optional[str] = Field(
        default=None,
        description="Custom log format string"
    )
    verbose: bool = Field(
        default=False,
        description="Enable verbose output"
    )
    
    class Config:
        """Pydantic configuration."""
        extra = "forbid"


class AppConfig(BaseModel):
    """Main application configuration combining all settings."""
    
    llm: LLMConfig = Field(
        default_factory=LLMConfig,
        description="LLM configuration"
    )
    story: StoryConfig = Field(
        default_factory=StoryConfig,
        description="Story generation configuration"
    )
    cache: CacheConfig = Field(
        default_factory=CacheConfig,
        description="Cache configuration"
    )
    output: OutputConfig = Field(
        default_factory=OutputConfig,
        description="Output configuration"
    )
    logging: LoggingConfig = Field(
        default_factory=LoggingConfig,
        description="Logging configuration"
    )
    recursion_limit: int = Field(
        default=200,
        ge=50, le=1000,
        description="LangGraph recursion limit"
    )
    
    @classmethod
    def from_args(cls, args) -> "AppConfig":
        """Create config from command line arguments.
        
        Args:
            args: Parsed command line arguments
            
        Returns:
            AppConfig instance
        """
        return cls(
            llm=LLMConfig(
                provider=args.model_provider,
                model=args.model,
            ),
            story=StoryConfig(
                genre=args.genre,
                tone=args.tone,
                language=args.language,
                author=args.author,
                initial_idea=args.idea,
            ),
            cache=CacheConfig(
                type=args.cache,
                path=Path(args.cache_path) if args.cache_path else None,
            ),
            output=OutputConfig(
                file_path=Path(args.output),
                save_info_file=args.info_file,
            ),
            logging=LoggingConfig(
                verbose=args.verbose,
            ),
            recursion_limit=args.recursion_limit,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for serialization.
        
        Returns:
            Dictionary representation of config
        """
        return self.dict(exclude_none=True)
    
    class Config:
        """Pydantic configuration."""
        extra = "forbid"
        validate_assignment = True