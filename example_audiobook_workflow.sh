#!/bin/bash
# Example workflow for generating an audiobook from a story

echo "=== StoryCraft Audiobook Generation Example ==="
echo

# Check if Azure credentials are set
if [ -z "$SPEECH_KEY" ] || [ -z "$SPEECH_REGION" ]; then
    echo "Error: Azure Speech Service credentials not set."
    echo "Please set the following environment variables:"
    echo "  export SPEECH_KEY='your-azure-speech-key'"
    echo "  export SPEECH_REGION='your-azure-region'"
    exit 1
fi

# Step 1: Generate a story with audiobook SSML (or use existing)
echo "Step 1: Generate story with audiobook content..."
echo "Choose an option:"
echo "1) Generate new story with audiobook"
echo "2) Convert existing story to audiobook"
read -p "Enter choice (1 or 2): " choice

if [ "$choice" = "1" ]; then
    # Generate new story
    echo
    echo "Generating new story with audiobook SSML..."
    nix develop -c python run_storyteller.py \
        --genre "mystery" \
        --tone "noir" \
        --language "english" \
        --audio-book \
        --verbose
elif [ "$choice" = "2" ]; then
    # Convert existing story
    echo
    echo "Converting existing story to audiobook SSML..."
    nix develop -c python run_storyteller.py --audio-book
else
    echo "Invalid choice. Exiting."
    exit 1
fi

echo
echo "Step 2: Generate audio files from SSML..."
echo

# Step 2: Generate audio files
nix develop -c python generate_audiobook.py \
    --output-dir audiobook_output \
    --format mp3

echo
echo "Step 3: (Optional) Concatenate audio files..."
echo

# Check if ffmpeg is available
if command -v ffmpeg &> /dev/null; then
    read -p "Do you want to concatenate all scenes into one audiobook? (y/n): " concat_choice
    
    if [ "$concat_choice" = "y" ] || [ "$concat_choice" = "Y" ]; then
        cd audiobook_output/scenes
        
        # Create file list
        ls *.mp3 | sort > filelist.txt
        
        # Concatenate files
        echo "Concatenating audio files..."
        ffmpeg -f concat -safe 0 -i filelist.txt -c copy ../full_audiobook.mp3
        
        echo "Full audiobook created: audiobook_output/full_audiobook.mp3"
        cd ../..
    fi
else
    echo "ffmpeg not found. To concatenate audio files, install ffmpeg."
fi

echo
echo "=== Audiobook generation complete! ==="
echo "Audio files are in: audiobook_output/scenes/"
echo
echo "Next steps:"
echo "1. Listen to the generated audio files"
echo "2. Try different voices with: generate_audiobook.py --voice 'voice-name'"
echo "3. Upload to audiobook platforms or use for personal listening"