"""Prompt template management for StoryCraft Agent.

This module provides a template-based system for managing prompts across different
languages using LangChain prompt templates and Jinja2.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape
from langchain.prompts import PromptTemplate

from storyteller_lib.core.config import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from storyteller_lib.core.logger import get_logger

logger = get_logger(__name__)


class PromptTemplateManager:
    """Manages prompt templates for different languages and operations."""

    def __init__(self, language: str = DEFAULT_LANGUAGE):
        """Initialize the template manager for a specific language.

        Args:
                language: The target language code (e.g., 'english', 'german')
        """
        self.language = language.lower()
        self.template_dir = Path(__file__).parent / "templates"
        logger.info(f"Initializing PromptTemplateManager for language: {self.language}")
        self.jinja_env = self._setup_jinja_environment()
        self._template_cache: dict[str, PromptTemplate] = {}

    def _setup_jinja_environment(self) -> Environment:
        """Set up the Jinja2 environment with proper loaders."""
        # Create loader that checks language-specific directory first, then base
        loaders = []

        # Add language-specific loader if not English
        if (
            self.language != "english"
        ):  # Always check against 'english', not DEFAULT_LANGUAGE
            lang_dir = self.template_dir / "languages" / self.language
            logger.info(f"Looking for language-specific templates in: {lang_dir}")
            if lang_dir.exists():
                logger.info(f"Found language directory for {self.language}")
                loaders.append(FileSystemLoader(str(lang_dir)))
                # List files in language directory for debugging
                template_files = list(lang_dir.glob("*.jinja2"))
                logger.info(
                    f"Found {len(template_files)} templates in {self.language} directory"
                )
                if len(template_files) < 10:
                    logger.debug(f"Templates: {[f.name for f in template_files]}")
            else:
                logger.warning(f"Language directory not found: {lang_dir}")

        # Always add base templates as fallback
        base_dir = self.template_dir / "base"
        if base_dir.exists():
            loaders.append(FileSystemLoader(str(base_dir)))
            logger.info("Added base template directory as fallback")

        # Create environment with all loaders
        from jinja2 import ChoiceLoader

        loader = (
            ChoiceLoader(loaders)
            if loaders
            else FileSystemLoader(str(self.template_dir))
        )

        env = Environment(
            loader=loader,
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Add custom filters
        env.filters["capitalize_first"] = lambda s: s[0].upper() + s[1:] if s else s

        # Add global variables
        env.globals.update(
            {
                "language": self.language,
                "language_name": SUPPORTED_LANGUAGES.get(self.language, self.language),
                "supported_languages": SUPPORTED_LANGUAGES,
            }
        )

        return env

    def get_template(self, template_name: str, **default_vars) -> PromptTemplate:
        """Get a LangChain PromptTemplate for the specified template.

        Args:
                template_name: Name of the template file (without .jinja2 extension)
            **default_vars: Default variables to include in the template

        Returns:
                LangChain PromptTemplate instance
        """
        cache_key = f"{self.language}:{template_name}"

        if cache_key in self._template_cache:
            return self._template_cache[cache_key]

        try:
            # Load Jinja2 template
            jinja_template = self.jinja_env.get_template(f"{template_name}.jinja2")

            # Extract variables from the template
            template_vars = self._extract_template_variables(jinja_template)

            # Render with empty variables to get the template string
            template_str = jinja_template.render(**default_vars)

            # Create LangChain PromptTemplate
            prompt_template = PromptTemplate(
                template=template_str,
                input_variables=[
                    var for var in template_vars if var not in default_vars
                ],
            )

            self._template_cache[cache_key] = prompt_template
            return prompt_template

        except TemplateNotFound:
            logger.error(
                f"Template '{template_name}' not found for language '{self.language}'"
            )
            # Return a basic template as fallback
            return PromptTemplate(
                template="Please provide content for {task}", input_variables=["task"]
            )

    def render(self, template_name: str, **kwargs) -> str:
        """Render a template with the provided variables.

        Args:
                template_name: Name of the template file (without .jinja2 extension)
            **kwargs: Variables to pass to the template

        Returns:
                Rendered template string
        """
        try:
            template = self.jinja_env.get_template(f"{template_name}.jinja2")
            logger.debug(
                f"Rendering template '{template_name}' for language '{self.language}'"
            )
            logger.debug(
                f"Template filename: {getattr(template, 'filename', 'Unknown')}"
            )

            # Log if we're getting the base template instead of language-specific
            template_path = getattr(template, "filename", "")
            if (
                self.language != DEFAULT_LANGUAGE
                and self.language != "english"
                and "/base/" in template_path
            ):
                logger.warning(
                    f"Using base template for '{template_name}' instead of {self.language}-specific template"
                )

            rendered = template.render(**kwargs)
            # Log first 100 chars of rendered template to verify language
            logger.debug(f"Rendered template starts with: {rendered[:100]}...")
            return rendered
        except TemplateNotFound:
            logger.error(
                f"Template '{template_name}' not found for language '{self.language}'"
            )
            return f"[Template {template_name} not found]"

    def _extract_template_variables(self, template) -> list[str]:
        """Extract variable names from a Jinja2 template.

        Args:
                template: Jinja2 template instance

        Returns:
                List of variable names used in the template
        """
        from jinja2 import meta

        ast = self.jinja_env.parse(template.source)
        return list(meta.find_undeclared_variables(ast))

    def list_available_templates(self) -> list[str]:
        """List all available templates for the current language.

        Returns:
                List of template names (without extensions)
        """
        templates = set()

        # Check language-specific directory
        if self.language != DEFAULT_LANGUAGE:
            lang_dir = self.template_dir / "languages" / self.language
            if lang_dir.exists():
                for file in lang_dir.glob("*.jinja2"):
                    templates.add(file.stem)

        # Check base directory
        base_dir = self.template_dir / "base"
        if base_dir.exists():
            for file in base_dir.glob("*.jinja2"):
                templates.add(file.stem)

        return sorted(templates)


# Singleton instances for each language
_template_managers: dict[str, PromptTemplateManager] = {}


def get_template_manager(language: str = DEFAULT_LANGUAGE) -> PromptTemplateManager:
    """Get or create a template manager for the specified language.

    Args:
        language: Target language code

    Returns:
        PromptTemplateManager instance
    """
    if language not in _template_managers:
        _template_managers[language] = PromptTemplateManager(language)
    return _template_managers[language]


# Convenience functions
def render_prompt(
    template_name: str, language: str = DEFAULT_LANGUAGE, **kwargs
) -> str:
    """Render a prompt template for the specified language.

    Args:
        template_name: Name of the template
        language: Target language
        **kwargs: Variables for the template

    Returns:
        Rendered prompt string
    """
    logger.info(
        f"render_prompt called with template_name='{template_name}', language='{language}'"
    )
    manager = get_template_manager(language)
    return manager.render(template_name, **kwargs)


def get_prompt_template(
    template_name: str, language: str = DEFAULT_LANGUAGE, **default_vars
) -> PromptTemplate:
    """Get a LangChain PromptTemplate for the specified language.

    Args:
        template_name: Name of the template
        language: Target language
        **default_vars: Default variables

    Returns:
        LangChain PromptTemplate instance
    """
    manager = get_template_manager(language)
    return manager.get_template(template_name, **default_vars)
