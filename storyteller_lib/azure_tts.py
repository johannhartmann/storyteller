"""
Azure Text-to-Speech utilities for batch processing and advanced features.

This module provides enhanced functionality for Azure TTS including:
- Batch synthesis for large volumes
- Progress callbacks
- Error recovery
- Voice configuration management
"""

import json
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable, Any
from pathlib import Path
import hashlib

import azure.cognitiveservices.speech as speechsdk

from storyteller_lib.logger import get_logger

logger = get_logger(__name__)


@dataclass
class VoiceConfig:
    """Configuration for a TTS voice."""
    name: str
    language: str
    gender: str
    style: Optional[str] = None
    style_degree: Optional[float] = None
    rate: Optional[str] = None
    pitch: Optional[str] = None
    

class VoiceManager:
    """Manages voice configurations for different languages and styles."""
    
    # Recommended voices for different languages and styles
    VOICE_RECOMMENDATIONS = {
        "english": {
            "narrator": {
                "male": ["en-US-AndrewMultilingualNeural", "en-US-GuyNeural"],
                "female": ["en-US-AvaMultilingualNeural", "en-US-JennyNeural"],
                "neutral": ["en-US-AriaNeural"]
            },
            "dramatic": {
                "male": ["en-US-DavisNeural"],
                "female": ["en-US-SaraNeural"]
            }
        },
        "german": {
            "narrator": {
                "male": ["de-DE-ConradNeural", "de-DE-KlausNeural"],
                "female": ["de-DE-SeraphinaMultilingualNeural", "de-DE-KatjaNeural"],
                "neutral": ["de-DE-AmalaNeural"]
            },
            "dramatic": {
                "male": ["de-DE-RalfNeural"],
                "female": ["de-DE-LouisaNeural"]
            }
        }
    }
    
    @classmethod
    def get_voice_for_language(cls, language: str, style: str = "narrator", 
                              gender: str = "neutral") -> str:
        """Get recommended voice for language, style and gender."""
        language = language.lower()
        style = style.lower()
        gender = gender.lower()
        
        if language not in cls.VOICE_RECOMMENDATIONS:
            logger.warning(f"No voice recommendations for language: {language}")
            return "en-US-JennyNeural"  # Default fallback
            
        style_voices = cls.VOICE_RECOMMENDATIONS[language].get(style, 
                      cls.VOICE_RECOMMENDATIONS[language]["narrator"])
        
        gender_voices = style_voices.get(gender, style_voices.get("neutral", []))
        
        if gender_voices:
            return gender_voices[0]
        else:
            # Fallback to any available voice
            for g in ["neutral", "female", "male"]:
                if g in style_voices and style_voices[g]:
                    return style_voices[g][0]
                    
        return "en-US-JennyNeural"  # Ultimate fallback


class BatchSynthesizer:
    """Handles batch synthesis of multiple SSML texts."""
    
    def __init__(self, speech_key: str, speech_region: str, 
                 output_format: str = "mp3"):
        """
        Initialize batch synthesizer.
        
        Args:
            speech_key: Azure Speech Service key
            speech_region: Azure Speech Service region  
            output_format: Audio format (mp3, wav)
        """
        self.speech_key = speech_key
        self.speech_region = speech_region
        self.output_format = output_format
        
        # Configure speech service
        self.speech_config = speechsdk.SpeechConfig(
            subscription=speech_key,
            region=speech_region
        )
        
        # Set output format
        if output_format.lower() == "mp3":
            self.speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
            )
        else:
            self.speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm
            )
            
    def synthesize_batch(self, ssml_items: List[Dict[str, Any]], 
                        output_dir: Path,
                        progress_callback: Optional[Callable[[int, int], None]] = None,
                        error_callback: Optional[Callable[[str, Exception], None]] = None) -> Dict[str, Any]:
        """
        Synthesize a batch of SSML texts.
        
        Args:
            ssml_items: List of dicts with 'id', 'ssml', and 'filename' keys
            output_dir: Directory for output files
            progress_callback: Optional callback for progress updates
            error_callback: Optional callback for errors
            
        Returns:
            Dictionary with results and statistics
        """
        results = {
            "successful": [],
            "failed": [],
            "total_duration_seconds": 0,
            "total_size_bytes": 0
        }
        
        total_items = len(ssml_items)
        start_time = time.time()
        
        for idx, item in enumerate(ssml_items):
            try:
                output_path = output_dir / item['filename']
                
                # Configure audio output
                audio_config = speechsdk.audio.AudioOutputConfig(
                    filename=str(output_path),
                    use_default_speaker=False
                )
                
                # Create synthesizer
                synthesizer = speechsdk.SpeechSynthesizer(
                    speech_config=self.speech_config,
                    audio_config=audio_config
                )
                
                # Synthesize SSML
                result = synthesizer.speak_ssml_async(item['ssml']).get()
                
                if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                    file_size = output_path.stat().st_size
                    results["successful"].append({
                        "id": item['id'],
                        "filename": item['filename'],
                        "path": str(output_path),
                        "size_bytes": file_size
                    })
                    results["total_size_bytes"] += file_size
                    
                    logger.info(f"Synthesized: {item['filename']} ({file_size / 1024:.1f} KB)")
                else:
                    error_msg = f"Synthesis failed: {result.reason}"
                    if result.reason == speechsdk.ResultReason.Canceled:
                        error_msg += f" - {result.cancellation_details.error_details}"
                        
                    results["failed"].append({
                        "id": item['id'],
                        "filename": item['filename'],
                        "error": error_msg
                    })
                    
                    if error_callback:
                        error_callback(item['id'], Exception(error_msg))
                        
            except Exception as e:
                logger.error(f"Error synthesizing {item.get('filename', 'unknown')}: {str(e)}")
                results["failed"].append({
                    "id": item.get('id'),
                    "filename": item.get('filename'),
                    "error": str(e)
                })
                
                if error_callback:
                    error_callback(item.get('id'), e)
                    
            # Progress callback
            if progress_callback:
                progress_callback(idx + 1, total_items)
                
            # Small delay to avoid rate limiting
            if idx < total_items - 1:
                time.sleep(0.3)
                
        results["total_duration_seconds"] = time.time() - start_time
        
        return results


class SSMLEnhancer:
    """Enhances SSML with additional speech features."""
    
    @staticmethod
    def add_voice_wrapper(ssml: str, voice_name: str, 
                         style: Optional[str] = None,
                         style_degree: Optional[float] = None) -> str:
        """
        Wrap SSML content with voice and style tags.
        
        Args:
            ssml: Original SSML content
            voice_name: Voice to use
            style: Optional speaking style
            style_degree: Style intensity (0.01 to 2.0)
            
        Returns:
            Enhanced SSML
        """
        # Extract content between speak tags if present
        if '<speak' in ssml and '</speak>' in ssml:
            start = ssml.find('>') + 1
            end = ssml.rfind('</speak>')
            content = ssml[start:end]
            
            # Extract speak tag attributes
            speak_start = ssml[:ssml.find('>') + 1]
        else:
            content = ssml
            speak_start = '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">'
            
        # Build voice tag
        voice_tag = f'<voice name="{voice_name}">'
        
        # Add style if specified
        if style:
            style_attrs = f'style="{style}"'
            if style_degree is not None:
                style_attrs += f' styledegree="{style_degree}"'
            content = f'<mstts:express-as {style_attrs}>{content}</mstts:express-as>'
            
        # Reconstruct SSML
        enhanced_ssml = f'{speak_start}\n{voice_tag}\n{content}\n</voice>\n</speak>'
        
        return enhanced_ssml
        
    @staticmethod
    def add_chapter_announcement(chapter_num: int, chapter_title: str,
                               voice_name: str, language: str = "en-US") -> str:
        """Create SSML for chapter announcement."""
        if language.startswith("de"):
            announcement = f"Kapitel {chapter_num}: {chapter_title}"
        else:
            announcement = f"Chapter {chapter_num}: {chapter_title}"
            
        return f"""<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{language}">
    <voice name="{voice_name}">
        <emphasis level="strong">{announcement}</emphasis>
        <break time="2000ms"/>
    </voice>
</speak>"""

    @staticmethod 
    def add_scene_transition(duration_ms: int = 1500) -> str:
        """Create SSML for scene transition pause."""
        return f'<break time="{duration_ms}ms"/>'


class AudioCache:
    """Simple cache for generated audio to avoid regenerating identical content."""
    
    def __init__(self, cache_dir: Path):
        """Initialize cache with directory."""
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def get_cache_key(self, ssml: str, voice: str) -> str:
        """Generate cache key from SSML and voice."""
        content = f"{ssml}|{voice}"
        return hashlib.sha256(content.encode()).hexdigest()
        
    def get_cached_file(self, ssml: str, voice: str) -> Optional[Path]:
        """Check if audio for this SSML exists in cache."""
        cache_key = self.get_cache_key(ssml, voice)
        cache_file = self.cache_dir / f"{cache_key}.mp3"
        
        if cache_file.exists():
            logger.debug(f"Cache hit for key: {cache_key}")
            return cache_file
            
        return None
        
    def save_to_cache(self, ssml: str, voice: str, audio_path: Path) -> Path:
        """Save audio file to cache."""
        cache_key = self.get_cache_key(ssml, voice)
        cache_file = self.cache_dir / f"{cache_key}.mp3"
        
        # Copy file to cache
        import shutil
        shutil.copy2(audio_path, cache_file)
        
        logger.debug(f"Saved to cache: {cache_key}")
        return cache_file