# StoryCraft Audio Generation

This document provides a quick reference for generating audiobooks from StoryCraft stories using Azure Text-to-Speech.

## Quick Start

### Prerequisites
```bash
# Set Azure credentials
export SPEECH_KEY="your-azure-speech-key"
export SPEECH_REGION="your-azure-region"  # e.g., "eastus"

# Install dependencies
nix develop
poetry install
```

### Option 1: Generate New Story with Audio

```bash
# Generate story with audiobook SSML
nix develop -c python run_storyteller.py \
    --genre sci-fi \
    --tone adventurous \
    --audio-book

# Then generate audio files
nix develop -c python generate_audiobook.py
```

### Option 2: Convert Existing Story

```bash
# Convert existing story to audiobook SSML
nix develop -c python run_storyteller.py --audio-book

# Generate audio files
nix develop -c python generate_audiobook.py
```

## Audio Generation Options

### Test Mode (Recommended First Step)
```bash
# Generate only Chapter 1, Scene 1 to test voice and settings
nix develop -c python generate_audiobook.py --test

# Test with a different voice
nix develop -c python generate_audiobook.py --test --voice "en-US-AndrewMultilingualNeural"
```

### Basic Usage
```bash
# Generate all scenes with default settings
nix develop -c python generate_audiobook.py

# Specify output directory
nix develop -c python generate_audiobook.py --output-dir my_audiobook

# Use specific voice
nix develop -c python generate_audiobook.py --voice "en-US-AndrewMultilingualNeural"

# Generate WAV instead of MP3
nix develop -c python generate_audiobook.py --format wav
```

### Advanced Options
```bash
# Use different database
nix develop -c python generate_audiobook.py --db-path /path/to/story.db

# Show statistics only
nix develop -c python generate_audiobook.py --stats
```

## Recommended Voices

### English
- **Female Narrator**: `en-US-JennyNeural` (default)
- **Male Narrator**: `en-US-AndrewMultilingualNeural`
- **Dramatic Female**: `en-US-SaraNeural`
- **Dramatic Male**: `en-US-DavisNeural`

### German
- **Female Narrator**: `de-DE-KatjaNeural` (default)
- **Male Narrator**: `de-DE-ConradNeural`
- **Dramatic Female**: `de-DE-LouisaNeural`
- **Dramatic Male**: `de-DE-RalfNeural`

## Output Structure

```
audiobook_output/
├── scenes/
│   ├── 001_chapter_01_scene_01.mp3
│   ├── 002_chapter_01_scene_02.mp3
│   ├── 003_chapter_02_scene_01.mp3
│   └── ...
└── chapters/
    └── (future: concatenated chapters)
```

**File Naming**: Files are prefixed with a 3-digit global scene number (001, 002, etc.) to ensure they play in the correct order when sorted alphabetically in any audio player or file browser.

## Concatenating Audio Files

### Using FFmpeg
```bash
# Concatenate all scenes
cd audiobook_output/scenes
ls *.mp3 | sort > filelist.txt
ffmpeg -f concat -safe 0 -i filelist.txt -c copy ../full_audiobook.mp3
```

### Using the Example Script
```bash
# Run the interactive workflow
./example_audiobook_workflow.sh
```

## Cost Estimation

- Azure Neural TTS: ~$16 per 1 million characters
- 100,000 word novel ≈ 600,000 characters ≈ $9.60
- Test with shorter stories first!

## Troubleshooting

### No SSML Content
```
Error: No scenes with SSML content found
```
**Fix**: Run with `--generate-ssml` or `--convert-to-ssml` first

### Authentication Failed
```
Error: Speech synthesis canceled: Error
```
**Fix**: Check `SPEECH_KEY` and `SPEECH_REGION` environment variables

### Voice Not Available
Some voices may not be available in your region. Check [Azure docs](https://docs.microsoft.com/azure/cognitive-services/speech-service/language-support) for availability.

## Tips

1. **Test First**: Always use `--test` mode to check voice quality before generating the full audiobook
2. **Voice Selection**: Try different voices with test mode to find the best match for your story
3. **Cost Control**: Test mode shows estimated cost per scene
4. **Caching**: The system caches generated audio to avoid regenerating identical content
5. **Batch Processing**: For very long books, process in batches to avoid timeouts

## Next Steps

- Experiment with different voices and styles
- Add background music or sound effects in post-production
- Share your audiobook on platforms like ACX or Findaway Voices
- Consider using Azure Batch Synthesis API for very large books

For detailed documentation, see [docs/audiobook_generation.md](docs/audiobook_generation.md)