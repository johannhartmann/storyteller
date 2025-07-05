# StoryCraft Agent

An autonomous AI-powered story writing system that generates complete, multi-chapter stories following flexible narrative structures. Built with LangGraph for orchestration, SQLite database for state and memory management, and support for multiple LLM providers.

**Version 3.0** - Now with research-driven worldbuilding, comprehensive plot thread tracking, character knowledge management, multi-language support, and professional audiobook generation.

## Quick Start

```bash
# Using Nix development environment (recommended)
nix develop

# Generate your first story
python run_storyteller.py --genre fantasy --tone epic

# Let AI choose everything for you
python run_storyteller.py --idea "A story about a detective who solves crimes using dreams"

# Generate a research-enhanced story
python run_storyteller.py --genre "science fiction" --tone philosophical --research-worldbuilding
```

## Features

### Core Story Generation
- **Flexible Narrative Structures**: Intelligently selects from 6 narrative structures (Hero's Journey, Three-Act, Kishōtenketsu, In Medias Res, Circular, Nonlinear/Mosaic)
- **Dynamic Story Length**: Page-based control with automatic chapter and scene distribution
- **Multi-Language Support**: Generate stories in 12 languages with language-specific templates
- **Author Style Emulation**: Analyzes and mimics the writing style of specified authors

### Advanced Story Management
- **Plot Thread Tracking**: Active management system that tracks, develops, and ensures resolution of narrative threads
- **Character Knowledge System**: Tracks what each character knows at any point to prevent inconsistencies
- **Scene Context Management**: Comprehensive "what happened until now" summaries for narrative coherence
- **Research-Driven Worldbuilding**: Optional web research integration for authentic world elements
- **Multi-Level Corrections**: Scene, chapter, style, and minor text corrections for polished output

### Technical Features
- **LangGraph Orchestration**: Robust workflow management with conditional edges and state transitions
- **SQLite State Persistence**: Complete story state saved to database for consistency
- **Multi-LLM Support**: Works with OpenAI, Anthropic, and Google Gemini models
- **Response Caching**: SQLite-based caching for improved performance and reduced API costs
- **Real-time Progress Tracking**: Detailed progress updates throughout generation
- **Professional Audiobook Generation**: SSML-based text-to-speech with Azure Cognitive Services

## Requirements

- Python 3.12+
- Nix (recommended) for development environment
- At least one of the following API keys:
  - Google Gemini API key (recommended)
  - OpenAI API key
  - Anthropic API key
- Optional:
  - Tavily API key (for research-driven worldbuilding)
  - Azure Speech Service credentials (for audiobook generation)

## Installation

### Using Nix (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/storyteller.git
cd storyteller

# Enter the Nix development environment
nix develop

# Dependencies are automatically installed via Nix
```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/johannhartmann/storyteller.git
cd storyteller

pip install poetry

# Install dependencies
poetry install

# Create and configure .env file
cp .env.example .env
# Edit .env and add your API keys
```

## Configuration

Create a `.env` file in the project root:

```bash
# LLM Provider API Keys (at least one required)
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Default Model Configuration
DEFAULT_MODEL_PROVIDER=gemini
DEFAULT_MODEL=gemini-2.5-flash

# Optional: Research Enhancement
TAVILY_API_KEY=your_tavily_api_key_here

# Optional: Audiobook Generation
SPEECH_KEY=your-azure-speech-key-here
SPEECH_REGION=your-azure-region-here  # e.g., eastus, westeurope

# Optional: Advanced Configuration
LANGGRAPH_RECURSION_LIMIT=200  # Increase for very complex stories
```

## Usage

### Basic Story Generation

```bash
# Generate a fantasy epic
python run_storyteller.py --genre fantasy --tone epic --output my_story.md

# Generate a mystery with specific author style
python run_storyteller.py --genre mystery --tone dark --author "Edgar Allan Poe"

# Generate a story in German
python run_storyteller.py --genre fantasy --tone epic --language german

# Generate with research-enhanced worldbuilding
python run_storyteller.py --genre "science fiction" --research-worldbuilding
```

### Command Line Options

#### Required (at least one):
- `--genre`: Story genre (e.g., fantasy, sci-fi, mystery, thriller, horror)
- `--idea`: Initial story idea (alternative to genre/tone)

#### Story Configuration:
- `--tone`: Story tone (e.g., epic, dark, humorous, philosophical)
- `--author`: Author style to emulate
- `--language`: Target language (default: english)
- `--structure`: Narrative structure (auto, hero_journey, three_act, kishotenketsu, in_medias_res, circular, nonlinear_mosaic)
- `--pages`: Target story length in pages (e.g., 200 for short novel, 400 for standard)

#### Technical Options:
- `--output`: Output file path (default: generated filename)
- `--model-provider`: LLM provider (openai, anthropic, gemini)
- `--model`: Specific model to use
- `--cache`: Cache type (memory, sqlite, none)
- `--cache-path`: Custom cache location
- `--recursion-limit`: LangGraph recursion limit (default: 200)
- `--verbose`: Show detailed progress

#### Advanced Features:
- `--research-worldbuilding`: Enable web research for worldbuilding
- `--audio-book`: Generate SSML markup for audiobook creation
- `--convert-existing`: Add SSML to existing story in database

### Supported Languages

- English (default)
- German (full template support)

### Example Workflows

#### Standard Novel with Research
```bash
# Generate a 400-page sci-fi novel with research-enhanced worldbuilding
python run_storyteller.py \
  --genre "science fiction" \
  --tone philosophical \
  --pages 400 \
  --research-worldbuilding \
  --verbose
```

#### Multi-Language Story
```bash
# Generate a German fantasy story in the style of Michael Ende
python run_storyteller.py \
  --genre fantasy \
  --tone whimsical \
  --author "Michael Ende" \
  --language german \
  --output "die_unendliche_geschichte_2.md"
```

#### Complete Audiobook Production
```bash
# Step 1: Generate story with SSML
python run_storyteller.py \
  --genre mystery \
  --tone suspenseful \
  --audio-book

# Step 2: Generate audio files
python generate_audiobook.py --voice "en-US-JennyNeural"
```

## Architecture

### Core Components

The system is organized into distinct modules under `storyteller_lib/`:

1. **API Layer** (`api/`): Public interface for story generation
2. **Workflow Nodes** (`workflow/nodes/`): LangGraph workflow components
3. **Generation Modules** (`generation/`): Creative content generation
4. **Analysis Tools** (`analysis/`): Consistency and quality checks
5. **Persistence Layer** (`persistence/`): Database and memory management
6. **Universe Building** (`universe/`): World and character management
7. **Prompt System** (`prompts/`): Multi-language template rendering

### LangGraph Workflow

The story generation follows a sophisticated graph-based workflow:

```
Initialize → Brainstorm → Select Structure → Generate Outline → 
Build World → Create Characters → Plan Chapters → 
[For each scene: Brainstorm → Write → Reflect → Revise → Update] →
Review Continuity → Compile Story
```

Key workflow features:
- **Conditional Edges**: Dynamic flow based on state
- **No Recursion**: Explicit state transitions prevent loops
- **State Persistence**: Every step saved to database
- **Error Recovery**: Graceful handling of failures

### State Management

Uses TypedDict classes for structured state:
- `StoryState`: Top-level container
- `CharacterProfile`: Character information and evolution
- `ChapterState`: Chapter structure and scenes
- `SceneState`: Scene content and metadata
- `PlotThread`: Narrative thread tracking

### Database Schema

SQLite database with tables for:
- Story configuration and metadata
- Chapters and scenes with full content
- Character profiles and knowledge states
- World elements and locations
- Plot threads and their status
- Memory anchors for consistency
- Progress tracking and logs

## Advanced Features

### Plot Thread Management

The system actively tracks narrative threads:
- **Identification**: Automatic extraction from written scenes
- **Classification**: Major, minor, and background threads
- **Status Tracking**: Introduced, developed, resolved, or abandoned
- **Integration**: Influences scene generation and ensures resolution

### Character Knowledge System

Prevents inconsistencies by tracking:
- What each character knows at any point
- How they learned the information
- Knowledge updates after each scene
- Prevents characters knowing things they shouldn't

### Research-Driven Worldbuilding

When enabled with `--research-worldbuilding`:
- Uses Tavily API for web research
- Creates authentic world elements based on real information
- Particularly useful for historical or technical accuracy
- Requires `TAVILY_API_KEY` in environment

### Correction Systems

Multiple levels of quality assurance:
1. **Scene Corrections**: Grammar, consistency, flow
2. **Chapter Corrections**: Overall coherence, pacing
3. **Style Corrections**: Maintain author voice throughout
4. **Minor Corrections**: Final polish and cleanup

## Audiobook Generation

### Setup

1. Get Azure Speech Service credentials
2. Add to `.env`:
   ```
   SPEECH_KEY=your-key
   SPEECH_REGION=your-region
   ```

### Generation Process

1. Generate story with SSML:
   ```bash
   python run_storyteller.py --genre fantasy --audio-book
   ```

2. Create audio files:
   ```bash
   python generate_audiobook.py
   ```

### Features

- Professional narration with voice modulation
- Chapter and scene organization
- Automatic voice selection by language
- Cost estimation before generation
- SSML markup for emphasis and pacing

## Development

### Using Nix Environment

```bash
# Enter development shell
nix develop

# Run with proper environment
nix develop -c python run_storyteller.py --genre fantasy
```

### Project Structure

```
storyteller/
├── run_storyteller.py          # Main CLI entry point
├── generate_audiobook.py       # TTS generation
├── storyteller_lib/            # Core library
│   ├── api/                    # Public API
│   ├── workflow/               # LangGraph nodes
│   ├── generation/             # Content generation
│   ├── analysis/               # Quality checks
│   └── ...                     # Other modules
├── flake.nix                   # Nix configuration
├── pyproject.toml              # Poetry dependencies
└── .env.example                # Environment template
```

### Debugging

- Story progress: `~/.storyteller/logs/story_progress.log`
- Database inspection: `~/.storyteller/story_database.db`
- Enable verbose mode with `--verbose` flag
- LangSmith integration available for tracing

## Contributing

When contributing:
1. Use the Nix development environment
2. Follow existing code patterns and conventions
3. Run code quality tools:
   - Format code: `black storyteller_lib/`
   - Lint code: `ruff check . --fix`
   - Find dead code: `vulture . vulture_whitelist.py --min-confidence 80`
4. Test changes with various story configurations
5. Update documentation as needed


## Acknowledgments

Built with:
- [LangGraph](https://github.com/langchain-ai/langgraph) for workflow orchestration
- [LangChain](https://github.com/langchain-ai/langchain) for LLM integration
- Multiple LLM providers for content generation
- Azure Cognitive Services for text-to-speech
