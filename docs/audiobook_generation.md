# Audiobook Generation Guide

This guide explains how to generate audiobooks from your StoryCraft stories using Azure Text-to-Speech.

## Prerequisites

1. **Azure Speech Service Account**
   - Sign up for [Azure Cognitive Services](https://azure.microsoft.com/en-us/services/cognitive-services/speech-services/)
   - Create a Speech resource
   - Get your subscription key and region

2. **Environment Setup**
   ```bash
   # Set environment variables
   export SPEECH_KEY="your-azure-speech-key"
   export SPEECH_REGION="your-azure-region"  # e.g., "eastus"
   ```

3. **Install Dependencies**
   ```bash
   nix develop
   poetry install
   ```

## Step 1: Generate SSML Content

Before generating audio, you need to convert your story to SSML format:

```bash
# Convert existing story to SSML
nix develop -c python run_storyteller.py --convert-to-ssml

# Or during story generation, add the flag
nix develop -c python run_storyteller.py --genre sci-fi --tone adventurous --generate-ssml
```

This will:
- Read each scene from the database
- Convert it to SSML format with appropriate pauses, emphasis, and prosody
- Store the SSML in the `content_ssml` column of the scenes table

## Step 2: Generate Audio Files

Use the audiobook generator to create audio files:

```bash
# Generate audio for all scenes
nix develop -c python generate_audiobook.py

# Specify custom output directory
nix develop -c python generate_audiobook.py --output-dir my_audiobook

# Use a specific voice
nix develop -c python generate_audiobook.py --voice "en-US-AndrewMultilingualNeural"

# Generate WAV files instead of MP3
nix develop -c python generate_audiobook.py --format wav
```

### Available Options

- `--db-path`: Path to story database (default: `~/.storyteller/story_database.db`)
- `--output-dir`: Output directory for audio files (default: `audiobook_output`)
- `--format`: Audio format - `mp3` or `wav` (default: `mp3`)
- `--voice`: Override voice selection
- `--speech-key`: Azure Speech key (if not in environment)
- `--speech-region`: Azure region (if not in environment)
- `--stats`: Show statistics only

## Output Structure

The generator creates the following directory structure:

```
audiobook_output/
├── scenes/
│   ├── chapter_01_scene_01.mp3
│   ├── chapter_01_scene_02.mp3
│   ├── chapter_02_scene_01.mp3
│   └── ...
└── chapters/
    └── (for future chapter concatenation)
```

## Recommended Voices

### English Voices
- **Narrator (Neutral)**: `en-US-AriaNeural`
- **Narrator (Female)**: `en-US-JennyNeural`, `en-US-AvaMultilingualNeural`
- **Narrator (Male)**: `en-US-AndrewMultilingualNeural`, `en-US-GuyNeural`
- **Dramatic**: `en-US-DavisNeural` (male), `en-US-SaraNeural` (female)

### German Voices
- **Narrator (Neutral)**: `de-DE-AmalaNeural`
- **Narrator (Female)**: `de-DE-KatjaNeural`, `de-DE-SeraphinaMultilingualNeural`
- **Narrator (Male)**: `de-DE-ConradNeural`, `de-DE-KlausNeural`
- **Dramatic**: `de-DE-RalfNeural` (male), `de-DE-LouisaNeural` (female)

## Concatenating Audio Files

To create a single audiobook file, you can use FFmpeg:

```bash
# Concatenate all scenes into one file
cd audiobook_output/scenes
ls *.mp3 | sort | sed 's/^/file /' > filelist.txt
ffmpeg -f concat -safe 0 -i filelist.txt -c copy ../full_audiobook.mp3

# Or concatenate by chapter
for i in 01 02 03; do
  ffmpeg -i "concat:chapter_${i}_scene_*.mp3" -acodec copy ../chapters/chapter_${i}.mp3
done
```

## Cost Considerations

Azure Text-to-Speech pricing:
- Neural voices: ~$16 per 1 million characters
- Each punctuation mark counts as a character
- Estimate: A 100,000 word novel ≈ 600,000 characters ≈ $9.60

Tips to reduce costs:
- Use caching (already implemented) to avoid regenerating identical content
- Test with shorter stories first
- Consider using standard voices for drafts

## Troubleshooting

### No SSML Content Found
```
Error: No scenes with SSML content found in database
```
**Solution**: Run SSML conversion first (see Step 1)

### Authentication Failed
```
Error: Speech synthesis canceled: Error
```
**Solution**: Check your SPEECH_KEY and SPEECH_REGION environment variables

### Rate Limiting
The script includes automatic delays between synthesis requests. If you still hit rate limits, you can modify the delay in the code.

### Voice Not Available
Some voices may not be available in all regions. Check the [Azure documentation](https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/language-support) for voice availability.

## Advanced Usage

### Batch Processing

For very long books, you might want to process in batches:

```python
from storyteller_lib.azure_tts import BatchSynthesizer

synthesizer = BatchSynthesizer(speech_key, speech_region)
results = synthesizer.synthesize_batch(ssml_items, output_dir)
```

### Custom SSML Enhancement

You can enhance SSML with additional features:

```python
from storyteller_lib.azure_tts import SSMLEnhancer

# Add voice styling
enhanced_ssml = SSMLEnhancer.add_voice_wrapper(
    ssml=original_ssml,
    voice_name="en-US-JennyNeural",
    style="cheerful",
    style_degree=1.5
)
```

## Next Steps

- Experiment with different voices to find the best match for your story
- Consider adding music or sound effects in post-production
- Use audio editing software to fine-tune the final audiobook
- Share your audiobook on platforms like ACX, Findaway Voices, or Authors Republic