#!/usr/bin/env python3
"""
Generate audiobook from SSML content in the story database using Azure Text-to-Speech.

This script reads SSML-formatted content from the story database and generates
audio files using Azure Cognitive Services Speech SDK.
"""

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import sqlite3

import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

from storyteller_lib.database.models import StoryDatabase
from storyteller_lib.logger import get_logger

logger = get_logger(__name__)

# Load environment variables
# Try to load from current directory first, then parent directory
env_path = Path('.env')
if not env_path.exists():
    env_path = Path(__file__).parent / '.env'
    
load_dotenv(env_path)

# Debug: Print if keys are loaded
if os.environ.get('SPEECH_KEY'):
    logger.info("SPEECH_KEY loaded from environment")
else:
    logger.warning("SPEECH_KEY not found in environment")

# Check for required Azure SDK files
import site

# Find where the Azure SDK is installed
for site_dir in site.getsitepackages():
    azure_path = Path(site_dir) / "azure" / "cognitiveservices" / "speech"
    if azure_path.exists():
        logger.info(f"Azure SDK found at: {azure_path}")
        
        # Check for required libpal files
        libpal_files = list(azure_path.glob("libpal_azure_c_shared*.so"))
        if libpal_files:
            logger.info(f"Found libpal files: {[f.name for f in libpal_files]}")
        else:
            logger.warning("WARNING: libpal_azure_c_shared*.so files not found! This will cause Error 27.")
            
        # List all .so files
        so_files = list(azure_path.glob("*.so"))
        logger.info(f"Total .so files in SDK: {len(so_files)}")
        break
else:
    logger.warning("Azure SDK installation not found in site packages")


class AudiobookGenerator:
    """Generates audiobook files from SSML content using Azure TTS."""
    
    def __init__(self, speech_key: str, speech_region: str, db_path: str, output_dir: str):
        """
        Initialize the audiobook generator.
        
        Args:
            speech_key: Azure Speech Service subscription key
            speech_region: Azure Speech Service region
            db_path: Path to the story database
            output_dir: Directory for output audio files
        """
        self.speech_key = speech_key
        self.speech_region = speech_region
        self.db = StoryDatabase(db_path)
        
        # Get story title and create output directory
        story_config = self.db.get_story_config()
        story_title = story_config.get('title', 'Untitled Story')
        # Clean title for folder name (remove special characters)
        clean_title = "".join(c for c in story_title if c.isalnum() or c in (' ', '-', '_')).strip()
        clean_title = clean_title.replace(' ', '_')
        
        self.output_dir = Path(output_dir) / clean_title
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure speech synthesizer
        logger.info(f"Initializing Azure Speech SDK with region: {speech_region}")
        logger.info(f"Azure SDK version: {speechsdk.__version__ if hasattr(speechsdk, '__version__') else 'Unknown'}")
        
        try:
            self.speech_config = speechsdk.SpeechConfig(
                subscription=speech_key,
                region=speech_region
            )
            logger.info("Speech config created successfully")
        except Exception as e:
            logger.error(f"Failed to create speech config: {str(e)}")
            raise
        
        # Set default voice based on language
        story_config = self.db.get_story_config()
        self.language = story_config.get('language', 'english').lower()
        self._set_voice()
        
    def _set_voice(self, voice_name: Optional[str] = None):
        """Set the synthesis voice based on language or explicit name."""
        if voice_name:
            self.speech_config.speech_synthesis_voice_name = voice_name
        elif self.language == 'german':
            # German voices
            self.speech_config.speech_synthesis_voice_name = "de-DE-SeraphinaMultilingualNeural"
        else:
            # English voices (default)
            self.speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"
            
        logger.info(f"Using voice: {self.speech_config.speech_synthesis_voice_name}")
        
    def _create_audio_filename(self, chapter_num: int, scene_num: int, 
                              chapter_title: str, format: str = "mp3") -> str:
        """Create a standardized filename for audio files.
        
        Format: 03-04-chapter_title.mp3
        where 03 is chapter number, 04 is scene number
        """
        # Clean chapter title for filename (remove special characters)
        clean_title = "".join(c for c in chapter_title if c.isalnum() or c in (' ', '-')).strip()
        clean_title = clean_title.replace(' ', '_').lower()
        
        return f"{chapter_num:02d}-{scene_num:02d}-{clean_title}.{format}"
            
    def _fix_ssml_language(self, ssml: str) -> str:
        """Fix SSML to ensure it has proper language attributes."""
        # Check if SSML has language attribute
        if '<speak' in ssml and 'xml:lang' not in ssml:
            # Add language attribute to speak tag
            lang_code = self._get_lang_code()
            ssml = ssml.replace('<speak>', f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{lang_code}">')
        
        return ssml
    
    def generate_scene_audio(self, scene_id: int, chapter_num: int, scene_num: int,
                           chapter_title: str, content_ssml: str, 
                           format: str = "mp3") -> Optional[str]:
        """
        Generate audio for a single scene.
        
        Args:
            scene_id: Database scene ID
            chapter_num: Chapter number
            scene_num: Scene number
            chapter_title: Chapter title for filename
            content_ssml: SSML-formatted content
            format: Audio format (mp3, wav)
            
        Returns:
            Path to generated audio file or None if failed
        """
        filename = self._create_audio_filename(chapter_num, scene_num, chapter_title, format)
        output_path = self.output_dir / filename
        
        # Fix SSML language attribute if needed (for existing SSML in database)
        content_ssml = self._fix_ssml_language(content_ssml)
        
        try:
            # Configure audio output
            if format.lower() == "mp3":
                audio_config = speechsdk.audio.AudioOutputConfig(
                    filename=str(output_path),
                    use_default_speaker=False
                )
                self.speech_config.set_speech_synthesis_output_format(
                    speechsdk.SpeechSynthesisOutputFormat.Audio24Khz96KBitRateMonoMp3
                )
            else:  # WAV format
                audio_config = speechsdk.audio.AudioOutputConfig(
                    filename=str(output_path),
                    use_default_speaker=False
                )
                self.speech_config.set_speech_synthesis_output_format(
                    speechsdk.SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm
                )
            
            # Create synthesizer with error handling
            try:
                logger.debug(f"Creating synthesizer for {filename}")
                logger.debug(f"Audio output path: {output_path}")
                logger.debug(f"Audio format: {format}")
                
                synthesizer = speechsdk.SpeechSynthesizer(
                    speech_config=self.speech_config,
                    audio_config=audio_config
                )
                logger.debug("Synthesizer created successfully")
            except Exception as e:
                logger.error(f"Failed to create synthesizer: {str(e)}")
                logger.error(f"Exception type: {type(e).__name__}")
                logger.error(f"Speech config - Region: {self.speech_config.region}, Voice: {self.speech_config.speech_synthesis_voice_name}")
                
                # Check if we can get more details about the error
                if hasattr(e, 'error_code'):
                    logger.error(f"Error code: {e.error_code}")
                if hasattr(e, 'error_details'):
                    logger.error(f"Error details: {e.error_details}")
                    
                raise
            
            # Synthesize SSML
            logger.debug(f"Starting synthesis for scene {scene_id}")
            
            # Log first 200 chars of SSML to check prosody settings
            logger.debug(f"SSML preview: {content_ssml[:200]}...")
            
            result = synthesizer.speak_ssml_async(content_ssml).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                file_size = output_path.stat().st_size
                logger.info(f"Generated audio for Chapter {chapter_num}, Scene {scene_num}: "
                          f"{filename} ({file_size / 1024 / 1024:.1f} MB)")
                return str(output_path)
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                logger.error(f"Speech synthesis canceled: {cancellation_details.reason}")
                if cancellation_details.reason == speechsdk.CancellationReason.Error:
                    logger.error(f"Error details: {cancellation_details.error_details}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating audio for scene {scene_id}: {str(e)}")
            return None
            
    def generate_first_scene_only(self, format: str = "mp3", voice: Optional[str] = None) -> Optional[str]:
        """
        Generate audio for only the first scene (test mode).
        
        Args:
            format: Audio format (mp3, wav)
            voice: Optional voice name override
            
        Returns:
            Path to generated audio file or None
        """
        if voice:
            self._set_voice(voice)
            
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get Chapter 1, Scene 1 specifically
            cursor.execute("""
                SELECT s.id, s.content_ssml, s.scene_number, 
                       c.chapter_number, c.title as chapter_title,
                       s.description, s.content
                FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                WHERE c.chapter_number = 1 AND s.scene_number = 1
                AND s.content_ssml IS NOT NULL
            """)
            
            scene = cursor.fetchone()
            
            if not scene:
                logger.warning("Chapter 1, Scene 1 not found or has no SSML content")
                print("Chapter 1, Scene 1 not found or has no SSML content.")
                print("Make sure you've generated SSML content first with --audio-book flag.")
                return None
                
            print(f"\n=== TEST MODE: Generating audio for Chapter 1, Scene 1 ===")
            print(f"Chapter Title: {scene['chapter_title']}")
            if scene['description']:
                print(f"Scene Description: {scene['description'][:100]}...")
            
            # Show preview of the actual text content
            if scene['content']:
                preview_length = 200
                content_preview = scene['content'][:preview_length]
                if len(scene['content']) > preview_length:
                    content_preview += "..."
                print(f"\nScene Preview: {content_preview}")
            
            print(f"\nSSML length: {len(scene['content_ssml'])} characters")
            print(f"Estimated cost: ${len(scene['content_ssml']) * 0.000016:.4f}")
            print("=" * 60)
            
            print(f"\nGenerating audio with voice: {self.speech_config.speech_synthesis_voice_name}...", end='', flush=True)
            
            audio_path = self.generate_scene_audio(
                scene_id=scene['id'],
                chapter_num=scene['chapter_number'],
                scene_num=scene['scene_number'],
                chapter_title=scene['chapter_title'],
                content_ssml=scene['content_ssml'],
                format=format
            )
            
            if audio_path:
                print(" ✓")
                file_size = Path(audio_path).stat().st_size
                duration_estimate = file_size / (16000 * 2)  # Rough estimate based on 16kHz mono
                
                print(f"\nTest audio generated successfully!")
                print(f"File: {audio_path}")
                print(f"Size: {file_size / 1024 / 1024:.2f} MB")
                print(f"Estimated duration: {duration_estimate / 60:.1f} minutes")
                
                print(f"\nYou can now listen to this file to check:")
                print(f"- Voice quality and suitability for your story")
                print(f"- SSML markup effectiveness (pauses, emphasis, etc.)")
                print(f"- Pronunciation and pacing")
                print(f"- Overall audio quality")
                
                print(f"\nTo try a different voice, run:")
                print(f"  nix develop -c python generate_audiobook.py --test --voice \"voice-name\"")
                print(f"\nTo generate all scenes, run without --test flag:")
                print(f"  nix develop -c python generate_audiobook.py")
            else:
                print(" ✗ Failed")
                
            return audio_path
    
    def generate_all_scenes(self, format: str = "mp3", voice: Optional[str] = None) -> List[str]:
        """
        Generate audio files for all scenes with SSML content.
        
        Args:
            format: Audio format (mp3, wav)
            voice: Optional voice name override
            
        Returns:
            List of generated audio file paths
        """
        if voice:
            self._set_voice(voice)
            
        generated_files = []
        
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get all scenes with SSML content
            cursor.execute("""
                SELECT s.id, s.content_ssml, s.scene_number, 
                       c.chapter_number, c.title as chapter_title
                FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                WHERE s.content_ssml IS NOT NULL
                ORDER BY c.chapter_number, s.scene_number
            """)
            
            scenes = cursor.fetchall()
            total_scenes = len(scenes)
            
            if total_scenes == 0:
                logger.warning("No scenes with SSML content found in database")
                print("No scenes with SSML content found. Run SSML conversion first.")
                return []
                
            print(f"\nGenerating audio for {total_scenes} scenes...")
            print("=" * 60)
            
            for idx, scene in enumerate(scenes, 1):
                print(f"\n[{idx}/{total_scenes}] Chapter {scene['chapter_number']}, "
                      f"Scene {scene['scene_number']}...", end='', flush=True)
                
                audio_path = self.generate_scene_audio(
                    scene_id=scene['id'],
                    chapter_num=scene['chapter_number'],
                    scene_num=scene['scene_number'],
                    chapter_title=scene['chapter_title'],
                    content_ssml=scene['content_ssml'],
                    format=format
                )
                
                if audio_path:
                    generated_files.append(audio_path)
                    print(" ✓")
                else:
                    print(" ✗ Failed")
                    
                # Small delay to avoid rate limiting
                if idx < total_scenes:
                    time.sleep(0.5)
                    
        print("\n" + "=" * 60)
        print(f"Audio generation complete: {len(generated_files)}/{total_scenes} successful")
        
        return generated_files
        
    def concatenate_chapter_audio(self, chapter_num: int, scene_files: List[str], 
                                format: str = "mp3") -> Optional[str]:
        """
        Concatenate scene audio files into a single chapter file.
        
        Note: This is a placeholder. Actual implementation would require
        audio processing library like pydub or ffmpeg.
        
        Args:
            chapter_num: Chapter number
            scene_files: List of scene audio file paths
            format: Output format
            
        Returns:
            Path to concatenated chapter audio or None
        """
        # TODO: Implement audio concatenation
        # This would require additional dependencies like pydub or ffmpeg-python
        logger.warning("Chapter concatenation not yet implemented. "
                      "Consider using ffmpeg command line tool to merge scene files.")
        
        return None
        
    def get_statistics(self) -> Dict[str, any]:
        """Get statistics about the audiobook generation."""
        stats = {
            'total_scenes': 0,
            'scenes_with_ssml': 0,
            'generated_audio_files': 0,
            'total_audio_size_mb': 0.0
        }
        
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            
            # Total scenes
            cursor.execute("SELECT COUNT(*) FROM scenes WHERE content IS NOT NULL")
            stats['total_scenes'] = cursor.fetchone()[0]
            
            # Scenes with SSML
            cursor.execute("SELECT COUNT(*) FROM scenes WHERE content_ssml IS NOT NULL")
            stats['scenes_with_ssml'] = cursor.fetchone()[0]
            
        # Count generated audio files
        audio_files = list(self.output_dir.glob("*.mp3")) + list(self.output_dir.glob("*.wav"))
        stats['generated_audio_files'] = len(audio_files)
        
        # Calculate total size
        total_size = sum(f.stat().st_size for f in audio_files)
        stats['total_audio_size_mb'] = total_size / 1024 / 1024
        
        return stats


def main():
    """Main entry point for the audiobook generator."""
    parser = argparse.ArgumentParser(
        description="Generate audiobook from SSML content using Azure Text-to-Speech"
    )
    
    parser.add_argument(
        "--db-path",
        type=str,
        default=os.path.expanduser("~/.storyteller/story_database.db"),
        help="Path to the story database (default: ~/.storyteller/story_database.db)"
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        default="audiobook_output",
        help="Directory for output audio files (default: audiobook_output)"
    )
    
    parser.add_argument(
        "--format",
        type=str,
        choices=["mp3", "wav"],
        default="mp3",
        help="Audio output format (default: mp3)"
    )
    
    parser.add_argument(
        "--voice",
        type=str,
        help="Override voice selection (e.g., en-US-AvaMultilingualNeural)"
    )
    
    parser.add_argument(
        "--speech-key",
        type=str,
        help="Azure Speech Service key (or set SPEECH_KEY env var)"
    )
    
    parser.add_argument(
        "--speech-region",
        type=str,
        help="Azure Speech Service region (or set SPEECH_REGION env var)"
    )
    
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show statistics only, don't generate audio"
    )
    
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode: only generate audio for the first scene"
    )
    
    args = parser.parse_args()
    
    # Get Azure credentials
    speech_key = args.speech_key or os.environ.get('SPEECH_KEY')
    speech_region = args.speech_region or os.environ.get('SPEECH_REGION')
    
    if not speech_key or not speech_region:
        print("Error: Azure Speech Service credentials not provided.")
        print("Set SPEECH_KEY and SPEECH_REGION environment variables or use --speech-key and --speech-region")
        sys.exit(1)
        
    # Log credential status (without showing the actual key)
    logger.info(f"Speech Key: {'*' * 8}{speech_key[-4:] if speech_key else 'NOT SET'}")
    logger.info(f"Speech Region: {speech_region}")
    
    # Log environment variables that might affect the SDK
    logger.info(f"SSL_CERT_FILE: {os.environ.get('SSL_CERT_FILE', 'NOT SET')}")
    logger.info(f"CURL_CA_BUNDLE: {os.environ.get('CURL_CA_BUNDLE', 'NOT SET')}")
    logger.info(f"LD_LIBRARY_PATH: {os.environ.get('LD_LIBRARY_PATH', 'NOT SET')}")
    
    # Check for required system libraries
    import subprocess
    try:
        # Check if libasound.so.2 is available
        result = subprocess.run(['ldconfig', '-p'], capture_output=True, text=True)
        if 'libasound.so.2' in result.stdout:
            logger.info("libasound.so.2 found in system")
        else:
            logger.warning("libasound.so.2 NOT found in ldconfig")
    except Exception as e:
        logger.warning(f"Could not check ldconfig: {e}")
        
    # Check if database exists
    if not Path(args.db_path).exists():
        print(f"Error: Database not found at {args.db_path}")
        sys.exit(1)
        
    try:
        # Initialize generator
        generator = AudiobookGenerator(
            speech_key=speech_key,
            speech_region=speech_region,
            db_path=args.db_path,
            output_dir=args.output_dir
        )
        
        if args.stats:
            # Show statistics only
            stats = generator.get_statistics()
            print("\nAudiobook Generation Statistics")
            print("=" * 40)
            print(f"Total scenes: {stats['total_scenes']}")
            print(f"Scenes with SSML: {stats['scenes_with_ssml']}")
            print(f"Generated audio files: {stats['generated_audio_files']}")
            print(f"Total audio size: {stats['total_audio_size_mb']:.1f} MB")
        else:
            # Generate audio files
            print(f"\nAudiobook Generator")
            print(f"Database: {args.db_path}")
            print(f"Output directory: {args.output_dir}")
            print(f"Format: {args.format}")
            
            if args.test:
                # Test mode - only generate first scene
                audio_file = generator.generate_first_scene_only(
                    format=args.format,
                    voice=args.voice
                )
                
                if audio_file:
                    print(f"\n✓ Test completed successfully")
                    print(f"\nTo generate all scenes, run without --test flag:")
                    print(f"  nix develop -c python generate_audiobook.py")
                else:
                    print("\n✗ Test failed")
            else:
                # Normal mode - generate all scenes
                generated_files = generator.generate_all_scenes(
                    format=args.format,
                    voice=args.voice
                )
                
                if generated_files:
                    print(f"\n✓ Successfully generated {len(generated_files)} audio files")
                    print(f"Output directory: {generator.output_dir}")
                    
                    # Show final statistics
                    stats = generator.get_statistics()
                    print(f"\nTotal audio size: {stats['total_audio_size_mb']:.1f} MB")
                else:
                    print("\n✗ No audio files were generated")
                
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        print(f"\nError: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()