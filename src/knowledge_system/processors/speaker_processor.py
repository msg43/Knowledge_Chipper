"""
Speaker Processing Module

Handles speaker data preparation, name suggestions, and assignment logic
for the diarization-based speaker identification system.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from ..logger import get_logger
from .base import BaseProcessor, ProcessorResult

logger = get_logger(__name__)


class SpeakerSegment(BaseModel):
    """Represents a single speaker segment with timing and content."""
    
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds") 
    text: str = Field(..., description="Transcript text for this segment")
    speaker_id: str = Field(..., description="Original speaker ID (e.g., SPEAKER_00)")
    confidence: float = Field(default=0.0, description="Confidence score for speaker assignment")


class SpeakerData(BaseModel):
    """Aggregated data for a single speaker across all segments."""
    
    speaker_id: str = Field(..., description="Original speaker ID")
    segments: List[SpeakerSegment] = Field(default_factory=list)
    total_duration: float = Field(default=0.0, description="Total speaking time in seconds")
    segment_count: int = Field(default=0, description="Number of segments")
    sample_texts: List[str] = Field(default_factory=list, description="Representative text samples")
    first_five_segments: List[Dict] = Field(default_factory=list, description="First 5 speaking segments with timestamps")
    suggested_name: Optional[str] = Field(default=None, description="AI-suggested name")
    confidence_score: float = Field(default=0.0, description="Confidence in suggestion")
    
    
class SpeakerAssignment(BaseModel):
    """Represents a user's assignment of a name to a speaker."""
    
    speaker_id: str = Field(..., description="Original speaker ID")
    assigned_name: str = Field(..., description="User-assigned name")
    confidence: float = Field(default=1.0, description="User confidence in assignment")
    timestamp: datetime = Field(default_factory=datetime.now)
    source_file: Optional[str] = Field(default=None, description="Source recording file")


class SpeakerProcessor(BaseProcessor):
    """Process diarization data for speaker identification and assignment."""
    
    def __init__(self):
        """Initialize the speaker processor."""
        super().__init__()
        self.name_patterns = self._compile_name_patterns()
        
    def _compile_name_patterns(self) -> Dict[str, re.Pattern]:
        """Compile regex patterns for name detection."""
        return {
            'self_introduction': re.compile(
                r'\b(?:I\'?m|my name is|this is|I am)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
                re.IGNORECASE
            ),
            'greeting': re.compile(
                r'\b(?:hi|hello|hey),?\s+(?:I\'?m|this is)\s+([A-Z][a-z]+)',
                re.IGNORECASE  
            ),
            'role_introduction': re.compile(
                r'\b(?:as the|I\'m the|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
                re.IGNORECASE
            ),
            'direct_address': re.compile(
                r'\b(?:thanks?|thank you),?\s+([A-Z][a-z]+)',
                re.IGNORECASE
            )
        }
    
    @property
    def supported_formats(self) -> List[str]:
        """Return supported input formats."""
        return ["diarization_segments", "transcript_data"]
    
    def validate_input(self, input_data: Any) -> bool:
        """
        Validate input data for speaker processing.
        
        Args:
            input_data: Input data to validate
            
        Returns:
            bool: True if input is valid
        """
        if not isinstance(input_data, dict):
            return False
        
        # Check for required keys
        required_keys = ["diarization_segments", "transcript_segments"]
        return all(key in input_data for key in required_keys)
    
    def process(self, input_data: Any, **kwargs) -> ProcessorResult:
        """
        Process speaker diarization data.
        
        Args:
            input_data: Dictionary containing diarization_segments and transcript_segments
            **kwargs: Additional processing options
            
        Returns:
            ProcessorResult: Processing result with speaker data
        """
        try:
            if not self.validate_input(input_data):
                return ProcessorResult(
                    success=False,
                    error="Invalid input data for speaker processing"
                )
            
            diarization_segments = input_data["diarization_segments"]
            transcript_segments = input_data["transcript_segments"]
            
            # Prepare speaker data
            speaker_data_list = self.prepare_speaker_data(diarization_segments, transcript_segments)
            
            return ProcessorResult(
                success=True,
                data={"speaker_data_list": speaker_data_list}
            )
            
        except Exception as e:
            logger.error(f"Error processing speaker data: {e}")
            return ProcessorResult(
                success=False,
                error=str(e)
            )
    
    def prepare_speaker_data(
        self, 
        diarization_segments: List[Dict[str, Any]], 
        transcript_segments: List[Dict[str, Any]]
    ) -> List[SpeakerData]:
        """
        Merge diarization and transcript data for speaker assignment.
        
        Args:
            diarization_segments: List of diarization segments with speaker IDs and timing
            transcript_segments: List of transcript segments with text and timing
            
        Returns:
            List of SpeakerData objects with aggregated information per speaker
        """
        try:
            logger.info(f"Preparing speaker data from {len(diarization_segments)} diarization segments and {len(transcript_segments)} transcript segments")
            
            # Create mapping of speakers to their segments
            speaker_map: Dict[str, SpeakerData] = {}
            
            # Process each diarization segment
            for diar_seg in diarization_segments:
                speaker_id = diar_seg.get('speaker', 'UNKNOWN')
                start_time = float(diar_seg.get('start', 0))
                end_time = float(diar_seg.get('end', 0))
                
                # Find overlapping transcript segments
                overlapping_text = self._find_overlapping_text(
                    start_time, end_time, transcript_segments
                )
                
                # Create speaker segment
                speaker_segment = SpeakerSegment(
                    start=start_time,
                    end=end_time,
                    text=overlapping_text,
                    speaker_id=speaker_id
                )
                
                # Add to speaker data
                if speaker_id not in speaker_map:
                    speaker_map[speaker_id] = SpeakerData(speaker_id=speaker_id)
                
                speaker_data = speaker_map[speaker_id]
                speaker_data.segments.append(speaker_segment)
                speaker_data.total_duration += (end_time - start_time)
                speaker_data.segment_count += 1
            
            # Generate sample texts and suggestions for each speaker
            for speaker_data in speaker_map.values():
                speaker_data.sample_texts = self._extract_sample_texts(speaker_data.segments)
                speaker_data.first_five_segments = self._extract_first_five_segments(speaker_data.segments)
                speaker_data.suggested_name, speaker_data.confidence_score = self._suggest_speaker_name(speaker_data)
            
            # Sort speakers by total speaking time (most active first)
            sorted_speakers = sorted(
                speaker_map.values(),
                key=lambda x: x.total_duration,
                reverse=True
            )
            
            logger.info(f"Prepared data for {len(sorted_speakers)} speakers")
            return sorted_speakers
            
        except Exception as e:
            logger.error(f"Error preparing speaker data: {e}")
            return []
    
    def _find_overlapping_text(
        self, 
        start_time: float, 
        end_time: float, 
        transcript_segments: List[Dict[str, Any]]
    ) -> str:
        """Find transcript text that overlaps with the given time range."""
        overlapping_texts = []
        
        for trans_seg in transcript_segments:
            trans_start = float(trans_seg.get('start', 0))
            trans_end = float(trans_seg.get('end', trans_start + 1))
            
            # Check for overlap
            if not (end_time <= trans_start or start_time >= trans_end):
                text = trans_seg.get('text', '').strip()
                if text:
                    overlapping_texts.append(text)
        
        return ' '.join(overlapping_texts)
    
    def _extract_sample_texts(self, segments: List[SpeakerSegment]) -> List[str]:
        """Extract representative text samples from speaker segments."""
        # Sort segments by length to get the most substantial ones
        sorted_segments = sorted(segments, key=lambda x: len(x.text), reverse=True)
        
        samples = []
        for segment in sorted_segments[:5]:  # Take up to 5 samples
            text = segment.text.strip()
            if len(text) > 20:  # Only include substantial text
                # Truncate if too long
                if len(text) > 150:
                    text = text[:147] + "..."
                samples.append(text)
            
            if len(samples) >= 3:  # Limit to 3 samples for UI
                break
        
        return samples
    
    def _extract_first_five_segments(self, segments: List[SpeakerSegment]) -> List[Dict]:
        """Extract first 5 speaking segments with timestamps for identification."""
        first_five = []
        
        for i, segment in enumerate(segments[:5]):
            segment_dict = {
                'text': segment.text,
                'start': segment.start_time,
                'end': segment.end_time,
                'sequence': i + 1
            }
            first_five.append(segment_dict)
        
        return first_five
    
    def _suggest_speaker_name(self, speaker_data: SpeakerData) -> Tuple[Optional[str], float]:
        """Generate AI-powered name suggestion for a speaker."""
        try:
            all_text = ' '.join([seg.text for seg in speaker_data.segments])
            
            # Try different name detection patterns
            for pattern_name, pattern in self.name_patterns.items():
                matches = pattern.findall(all_text)
                if matches:
                    # Take the most common match
                    name_counts = {}
                    for match in matches:
                        name = match.strip().title()
                        name_counts[name] = name_counts.get(name, 0) + 1
                    
                    if name_counts:
                        suggested_name = max(name_counts, key=name_counts.get)
                        confidence = min(0.9, name_counts[suggested_name] / len(matches))
                        
                        logger.debug(f"Found name suggestion '{suggested_name}' with confidence {confidence:.2f} using pattern '{pattern_name}'")
                        return suggested_name, confidence
            
            # Fallback: analyze speech patterns for generic suggestions
            return self._analyze_speech_patterns(speaker_data)
            
        except Exception as e:
            logger.warning(f"Error suggesting speaker name: {e}")
            return None, 0.0
    
    def _analyze_speech_patterns(self, speaker_data: SpeakerData) -> Tuple[Optional[str], float]:
        """Analyze speech patterns to suggest generic speaker types."""
        all_text = ' '.join([seg.text for seg in speaker_data.segments]).lower()
        
        # Analyze formality and role indicators
        formal_indicators = ['furthermore', 'therefore', 'consequently', 'regarding', 'pursuant']
        informal_indicators = ['yeah', 'um', 'like', 'you know', 'basically']
        
        formal_count = sum(1 for indicator in formal_indicators if indicator in all_text)
        informal_count = sum(1 for indicator in informal_indicators if indicator in all_text)
        
        # Check for leadership/authority indicators
        leadership_indicators = ['we need to', 'let\'s', 'our goal', 'moving forward', 'next steps']
        leadership_count = sum(1 for indicator in leadership_indicators if indicator in all_text)
        
        # Generate suggestion based on patterns
        if leadership_count > 2:
            return "Meeting Leader", 0.6
        elif formal_count > informal_count and formal_count > 1:
            return "Presenter", 0.5
        elif speaker_data.total_duration > 300:  # More than 5 minutes
            return "Main Speaker", 0.4
        else:
            return "Participant", 0.3
    
    def apply_speaker_assignments(
        self, 
        transcript_data: Dict[str, Any], 
        assignments: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Apply user-assigned names to transcript data.
        
        Args:
            transcript_data: Original transcript data with speaker IDs
            assignments: Dictionary mapping speaker IDs to assigned names
            
        Returns:
            Updated transcript data with real names
        """
        try:
            logger.info(f"Applying speaker assignments: {assignments}")
            
            updated_data = transcript_data.copy()
            
            # Update segments with assigned names
            if 'segments' in updated_data:
                for segment in updated_data['segments']:
                    speaker_id = segment.get('speaker')
                    if speaker_id and speaker_id in assignments:
                        segment['speaker'] = assignments[speaker_id]
                        segment['original_speaker_id'] = speaker_id  # Keep original for reference
            
            # Add assignment metadata
            updated_data['speaker_assignments'] = assignments
            updated_data['assignment_timestamp'] = datetime.now().isoformat()
            
            logger.info(f"Successfully applied assignments to {len(updated_data.get('segments', []))} segments")
            return updated_data
            
        except Exception as e:
            logger.error(f"Error applying speaker assignments: {e}")
            return transcript_data
    
    def generate_speaker_color_map(self, speaker_ids: List[str]) -> Dict[str, str]:
        """Generate consistent color mapping for speakers."""
        colors = [
            '#FF6B6B',  # Red
            '#4ECDC4',  # Teal
            '#45B7D1',  # Blue  
            '#96CEB4',  # Green
            '#FFEAA7',  # Yellow
            '#DDA0DD',  # Plum
            '#98D8C8',  # Mint
            '#F7DC6F',  # Light Yellow
            '#BB8FCE',  # Light Purple
            '#85C1E9'   # Light Blue
        ]
        
        color_map = {}
        for i, speaker_id in enumerate(sorted(speaker_ids)):
            color_map[speaker_id] = colors[i % len(colors)]
        
        return color_map
    
    def process(
        self, 
        input_data: Any, 
        dry_run: bool = False, 
        **kwargs: Any
    ) -> ProcessorResult:
        """
        Process speaker data for identification.
        
        Args:
            input_data: Dictionary containing diarization_segments and transcript_segments
            dry_run: If True, don't make actual changes
            **kwargs: Additional processing options
            
        Returns:
            ProcessorResult with prepared speaker data
        """
        try:
            if isinstance(input_data, dict):
                diarization_segments = input_data.get('diarization_segments', [])
                transcript_segments = input_data.get('transcript_segments', [])
            else:
                logger.error("Input data must be a dictionary with diarization_segments and transcript_segments")
                return ProcessorResult(
                    success=False,
                    errors=["Invalid input data format"]
                )
            
            if not diarization_segments:
                logger.warning("No diarization segments provided")
                return ProcessorResult(
                    success=False,
                    errors=["No diarization segments to process"]
                )
            
            # Prepare speaker data
            speaker_data = self.prepare_speaker_data(diarization_segments, transcript_segments)
            
            if not speaker_data:
                return ProcessorResult(
                    success=False,
                    errors=["Failed to prepare speaker data"]
                )
            
            # Generate color mapping
            speaker_ids = [speaker.speaker_id for speaker in speaker_data]
            color_map = self.generate_speaker_color_map(speaker_ids)
            
            result_data = {
                'speakers': [speaker.dict() for speaker in speaker_data],
                'color_map': color_map,
                'total_speakers': len(speaker_data),
                'processing_timestamp': datetime.now().isoformat()
            }
            
            return ProcessorResult(
                success=True,
                data=result_data,
                metadata={
                    'speakers_found': len(speaker_data),
                    'total_segments': sum(speaker.segment_count for speaker in speaker_data),
                    'total_duration': sum(speaker.total_duration for speaker in speaker_data)
                }
            )
            
        except Exception as e:
            logger.error(f"Speaker processing failed: {e}")
            return ProcessorResult(
                success=False,
                errors=[str(e)]
            )
