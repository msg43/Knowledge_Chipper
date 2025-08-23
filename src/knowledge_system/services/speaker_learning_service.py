"""
Speaker Learning Service

Provides intelligent speaker learning and pattern recognition capabilities
for the speaker identification system. Handles voice pattern learning,
speaker consistency analysis, and automatic suggestions.
"""

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from ..database.speaker_models import (
    get_speaker_db_service,
    SpeakerVoiceModel,
    SpeakerAssignmentModel,
    SpeakerLearningModel
)
from ..logger import get_logger
from ..processors.speaker_processor import SpeakerData
from ..utils.speaker_intelligence import SpeakerNameSuggester

logger = get_logger(__name__)


class SpeakerSuggestion(BaseModel):
    """Represents a speaker name suggestion with confidence and context."""
    
    name: str = Field(..., description="Suggested speaker name")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    source: str = Field(..., description="Source of suggestion (e.g., 'self_introduction', 'learned_pattern')")
    context: Optional[str] = Field(default=None, description="Context that led to this suggestion")
    
    def is_valid(self) -> bool:
        """Check if the suggestion is valid."""
        return len(self.name.strip()) > 0 and 0.0 <= self.confidence <= 1.0


class VoicePattern:
    """Represents a voice pattern for speaker recognition."""
    
    def __init__(self, speaker_name: str):
        """
        Initialize voice pattern.
        
        Args:
            speaker_name: Name of the speaker
        """
        self.speaker_name = speaker_name
        self.speech_characteristics = {}
        self.usage_count = 0
        self.confidence_scores = []
        self.last_updated = datetime.now()
        
        # Speech pattern features (placeholder for future audio analysis)
        self.features = {
            'avg_segment_length': 0.0,
            'speech_rate': 0.0,  # Words per minute
            'formality_score': 0.0,  # 0-1 scale
            'vocabulary_complexity': 0.0,  # 0-1 scale
            'common_phrases': [],
            'speaking_style_indicators': []
        }
    
    def update_from_speaker_data(self, speaker_data: SpeakerData):
        """
        Update voice pattern from speaker data.
        
        Args:
            speaker_data: SpeakerData object with speech information
        """
        try:
            # Update basic statistics
            if speaker_data.segments:
                total_text_length = sum(len(seg.text) for seg in speaker_data.segments)
                self.features['avg_segment_length'] = total_text_length / len(speaker_data.segments)
                
                # Estimate speech rate (rough approximation)
                if speaker_data.total_duration > 0:
                    word_count = sum(len(seg.text.split()) for seg in speaker_data.segments)
                    self.features['speech_rate'] = (word_count / speaker_data.total_duration) * 60
            
            # Analyze speech patterns
            all_text = ' '.join([seg.text for seg in speaker_data.segments])
            self._analyze_speech_patterns(all_text)
            
            # Update metadata
            self.usage_count += 1
            self.confidence_scores.append(speaker_data.confidence_score)
            self.last_updated = datetime.now()
            
            logger.debug(f"Updated voice pattern for {self.speaker_name}")
            
        except Exception as e:
            logger.error(f"Error updating voice pattern: {e}")
    
    def _analyze_speech_patterns(self, text: str):
        """Analyze speech patterns from text."""
        try:
            text_lower = text.lower()
            
            # Formality analysis
            formal_indicators = ['furthermore', 'therefore', 'consequently', 'regarding', 'pursuant', 'however']
            informal_indicators = ['yeah', 'um', 'like', 'you know', 'basically', 'kinda']
            
            formal_count = sum(1 for indicator in formal_indicators if indicator in text_lower)
            informal_count = sum(1 for indicator in informal_indicators if indicator in text_lower)
            
            total_indicators = formal_count + informal_count
            if total_indicators > 0:
                self.features['formality_score'] = formal_count / total_indicators
            
            # Vocabulary complexity (simple heuristic)
            words = text_lower.split()
            if words:
                avg_word_length = sum(len(word) for word in words) / len(words)
                self.features['vocabulary_complexity'] = min(1.0, avg_word_length / 10.0)
            
            # Common phrases (extract frequent 2-3 word combinations)
            self._extract_common_phrases(text_lower)
            
        except Exception as e:
            logger.warning(f"Error analyzing speech patterns: {e}")
    
    def _extract_common_phrases(self, text: str):
        """Extract common phrases from text."""
        try:
            words = text.split()
            if len(words) < 2:
                return
            
            # Extract 2-word phrases
            bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words)-1)]
            bigram_counts = Counter(bigrams)
            
            # Store most common phrases
            common_bigrams = [phrase for phrase, count in bigram_counts.most_common(5) if count > 1]
            self.features['common_phrases'] = common_bigrams
            
        except Exception as e:
            logger.warning(f"Error extracting common phrases: {e}")
    
    def get_similarity_score(self, other_pattern: 'VoicePattern') -> float:
        """
        Calculate similarity score with another voice pattern.
        
        Args:
            other_pattern: Another VoicePattern to compare with
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        try:
            if not isinstance(other_pattern, VoicePattern):
                return 0.0
            
            similarity_scores = []
            
            # Compare speech rate
            if (self.features['speech_rate'] > 0 and other_pattern.features['speech_rate'] > 0):
                rate_diff = abs(self.features['speech_rate'] - other_pattern.features['speech_rate'])
                max_rate = max(self.features['speech_rate'], other_pattern.features['speech_rate'])
                rate_similarity = 1.0 - (rate_diff / max_rate) if max_rate > 0 else 0.0
                similarity_scores.append(rate_similarity)
            
            # Compare formality
            formality_diff = abs(self.features['formality_score'] - other_pattern.features['formality_score'])
            formality_similarity = 1.0 - formality_diff
            similarity_scores.append(formality_similarity)
            
            # Compare vocabulary complexity
            vocab_diff = abs(self.features['vocabulary_complexity'] - other_pattern.features['vocabulary_complexity'])
            vocab_similarity = 1.0 - vocab_diff
            similarity_scores.append(vocab_similarity)
            
            # Compare common phrases
            phrase_similarity = self._calculate_phrase_similarity(other_pattern)
            similarity_scores.append(phrase_similarity)
            
            # Return weighted average
            if similarity_scores:
                return sum(similarity_scores) / len(similarity_scores)
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating similarity score: {e}")
            return 0.0
    
    def _calculate_phrase_similarity(self, other_pattern: 'VoicePattern') -> float:
        """Calculate similarity based on common phrases."""
        try:
            my_phrases = set(self.features.get('common_phrases', []))
            other_phrases = set(other_pattern.features.get('common_phrases', []))
            
            if not my_phrases and not other_phrases:
                return 1.0  # Both have no phrases, consider similar
            
            if not my_phrases or not other_phrases:
                return 0.0  # One has phrases, other doesn't
            
            # Jaccard similarity
            intersection = len(my_phrases.intersection(other_phrases))
            union = len(my_phrases.union(other_phrases))
            
            return intersection / union if union > 0 else 0.0
            
        except Exception as e:
            logger.warning(f"Error calculating phrase similarity: {e}")
            return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert voice pattern to dictionary for storage."""
        return {
            'speaker_name': self.speaker_name,
            'features': self.features,
            'usage_count': self.usage_count,
            'confidence_scores': self.confidence_scores,
            'last_updated': self.last_updated.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VoicePattern':
        """Create voice pattern from dictionary."""
        pattern = cls(data['speaker_name'])
        pattern.features = data.get('features', {})
        pattern.usage_count = data.get('usage_count', 0)
        pattern.confidence_scores = data.get('confidence_scores', [])
        
        last_updated_str = data.get('last_updated')
        if last_updated_str:
            try:
                pattern.last_updated = datetime.fromisoformat(last_updated_str)
            except ValueError:
                pattern.last_updated = datetime.now()
        
        return pattern


class SpeakerLearningService:
    """Service for intelligent speaker learning and suggestions."""
    
    def __init__(self):
        """Initialize the speaker learning service."""
        self.db_service = get_speaker_db_service()
        self.name_suggester = SpeakerNameSuggester()
        self.voice_patterns: Dict[str, VoicePattern] = {}
        self._load_voice_patterns()
    
    def _load_voice_patterns(self):
        """Load existing voice patterns from database."""
        try:
            # Get all speaker voices from database
            voices = self.db_service.find_matching_voices({}, threshold=0.0)  # Get all
            
            for voice in voices:
                if voice.voice_fingerprint:
                    try:
                        pattern_data = json.loads(voice.voice_fingerprint)
                        if isinstance(pattern_data, dict) and 'speaker_name' in pattern_data:
                            pattern = VoicePattern.from_dict(pattern_data)
                            self.voice_patterns[voice.name] = pattern
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning(f"Error loading voice pattern for {voice.name}: {e}")
            
            logger.info(f"Loaded {len(self.voice_patterns)} voice patterns")
            
        except Exception as e:
            logger.error(f"Error loading voice patterns: {e}")
    
    def learn_speaker_voice(self, speaker_name: str, speaker_data: SpeakerData) -> bool:
        """
        Learn voice characteristics for a speaker.
        
        Args:
            speaker_name: Name of the speaker
            speaker_data: SpeakerData with speech information
            
        Returns:
            True if learning was successful
        """
        try:
            # Get or create voice pattern
            if speaker_name not in self.voice_patterns:
                self.voice_patterns[speaker_name] = VoicePattern(speaker_name)
            
            pattern = self.voice_patterns[speaker_name]
            
            # Update pattern with new data
            pattern.update_from_speaker_data(speaker_data)
            
            # Save to database
            self._save_voice_pattern(pattern)
            
            logger.info(f"Learned voice pattern for {speaker_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error learning speaker voice: {e}")
            return False
    
    def _save_voice_pattern(self, pattern: VoicePattern):
        """Save voice pattern to database."""
        try:
            # Convert pattern to JSON
            pattern_json = json.dumps(pattern.to_dict())
            
            # Create or update voice model
            voice_data = SpeakerVoiceModel(
                name=pattern.speaker_name,
                voice_fingerprint={'pattern_data': pattern_json},
                usage_count=pattern.usage_count,
                last_used=pattern.last_updated
            )
            
            # Check if voice already exists
            existing_voice = self.db_service.get_speaker_voice_by_name(pattern.speaker_name)
            if existing_voice:
                # Update usage count
                self.db_service.update_voice_usage(existing_voice.id)
            else:
                # Create new voice
                self.db_service.create_speaker_voice(voice_data)
            
        except Exception as e:
            logger.error(f"Error saving voice pattern: {e}")
    
    def find_similar_speakers(
        self, 
        speaker_data: SpeakerData, 
        similarity_threshold: float = 0.7
    ) -> List[Tuple[str, float]]:
        """
        Find speakers similar to the given speaker data.
        
        Args:
            speaker_data: SpeakerData to find matches for
            similarity_threshold: Minimum similarity score
            
        Returns:
            List of (speaker_name, similarity_score) tuples
        """
        try:
            # Create temporary pattern for comparison
            temp_pattern = VoicePattern("temp")
            temp_pattern.update_from_speaker_data(speaker_data)
            
            similar_speakers = []
            
            for name, pattern in self.voice_patterns.items():
                similarity = temp_pattern.get_similarity_score(pattern)
                if similarity >= similarity_threshold:
                    similar_speakers.append((name, similarity))
            
            # Sort by similarity score (highest first)
            similar_speakers.sort(key=lambda x: x[1], reverse=True)
            
            logger.debug(f"Found {len(similar_speakers)} similar speakers")
            return similar_speakers
            
        except Exception as e:
            logger.error(f"Error finding similar speakers: {e}")
            return []
    
    def suggest_speaker_names(
        self, 
        speaker_data_list: List[SpeakerData],
        folder_path: Optional[Path] = None
    ) -> Dict[str, Tuple[str, float]]:
        """
        Suggest speaker names for a list of speakers.
        
        Args:
            speaker_data_list: List of SpeakerData objects
            folder_path: Optional folder path for context
            
        Returns:
            Dictionary mapping speaker IDs to (suggested_name, confidence) tuples
        """
        try:
            suggestions = {}
            
            # Get folder-level suggestions if available
            folder_suggestions = []
            if folder_path:
                folder_analysis = self.analyze_folder_speakers(folder_path)
                folder_suggestions = folder_analysis.get('suggestions', [])
            
            for i, speaker_data in enumerate(speaker_data_list):
                # Try voice pattern matching first
                similar_speakers = self.find_similar_speakers(speaker_data, similarity_threshold=0.6)
                
                if similar_speakers:
                    # Use most similar speaker
                    suggested_name, confidence = similar_speakers[0]
                    suggestions[speaker_data.speaker_id] = (suggested_name, confidence)
                elif folder_suggestions and i < len(folder_suggestions):
                    # Use folder-level suggestion
                    folder_suggestion = folder_suggestions[i]
                    suggestions[speaker_data.speaker_id] = (
                        folder_suggestion['name'], 
                        folder_suggestion['confidence']
                    )
                else:
                    # Use context-based suggestion from name suggester
                    context_suggestions = self.name_suggester.suggest_names_from_context(
                        speaker_data.sample_texts
                    )
                    
                    if context_suggestions:
                        suggested_name, confidence = context_suggestions[0]
                        suggestions[speaker_data.speaker_id] = (suggested_name, confidence)
                    else:
                        # Generic fallback
                        speaker_num = speaker_data.speaker_id.replace("SPEAKER_", "")
                        try:
                            num = int(speaker_num) + 1
                            suggestions[speaker_data.speaker_id] = (f"Speaker {num}", 0.3)
                        except ValueError:
                            suggestions[speaker_data.speaker_id] = ("Unknown Speaker", 0.1)
            
            logger.info(f"Generated suggestions for {len(suggestions)} speakers")
            return suggestions
            
        except Exception as e:
            logger.error(f"Error suggesting speaker names: {e}")
            return {}
    
    def analyze_folder_speakers(self, folder_path: Path) -> Dict[str, Any]:
        """
        Analyze speaker consistency across multiple recordings in a folder.
        
        Args:
            folder_path: Path to folder containing recordings
            
        Returns:
            Analysis results with suggested consistent speakers
        """
        try:
            # Get all assignments in the folder
            assignments = []
            recording_files = []
            
            # Look for audio files in the folder
            audio_extensions = ['.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac']
            for ext in audio_extensions:
                recording_files.extend(folder_path.glob(f"*{ext}"))
            
            # Get assignments for each recording
            for audio_file in recording_files:
                file_assignments = self.db_service.get_assignments_for_recording(str(audio_file))
                assignments.extend(file_assignments)
            
            if not assignments:
                return {'consistent_speakers': [], 'suggestions': []}
            
            # Analyze name frequency and patterns
            name_counts = Counter([assignment.assigned_name for assignment in assignments])
            speaker_id_patterns = defaultdict(list)
            
            # Group by speaker ID patterns
            for assignment in assignments:
                speaker_id_patterns[assignment.speaker_id].append(assignment.assigned_name)
            
            # Find consistent speakers (appear in multiple recordings)
            consistent_speakers = []
            suggestions = []
            
            for name, count in name_counts.most_common():
                if count > 1:  # Appears in multiple recordings
                    consistent_speakers.append(name)
                    
                    # Calculate confidence based on frequency and consistency
                    confidence = min(0.9, count * 0.2)
                    suggestions.append({
                        'name': name,
                        'frequency': count,
                        'confidence': confidence
                    })
            
            # Analyze speaker ID consistency
            consistent_id_mappings = {}
            for speaker_id, names in speaker_id_patterns.items():
                name_counts_for_id = Counter(names)
                most_common_name, frequency = name_counts_for_id.most_common(1)[0]
                
                # If this speaker ID consistently maps to the same name
                if frequency > 1 and frequency / len(names) > 0.6:
                    consistent_id_mappings[speaker_id] = most_common_name
            
            return {
                'consistent_speakers': consistent_speakers,
                'suggestions': suggestions[:5],  # Top 5 suggestions
                'total_recordings': len(set(assignment.recording_path for assignment in assignments)),
                'unique_speakers': len(name_counts),
                'consistent_id_mappings': consistent_id_mappings
            }
            
        except Exception as e:
            logger.error(f"Error analyzing folder speakers: {e}")
            return {'consistent_speakers': [], 'suggestions': []}
    
    def learn_from_user_corrections(
        self, 
        original_suggestion: str, 
        user_correction: str, 
        context: Dict[str, Any]
    ):
        """
        Learn from user corrections to improve future suggestions.
        
        Args:
            original_suggestion: Original AI suggestion
            user_correction: User's correction
            context: Context information about the correction
        """
        try:
            # Create learning entry
            learning_data = SpeakerLearningModel(
                original_suggestion=original_suggestion,
                user_correction=user_correction,
                context_data=context,
                learning_weight=1.0
            )
            
            # Save to database
            self.db_service.create_learning_entry(learning_data)
            
            # Update voice patterns if applicable
            if user_correction in self.voice_patterns:
                pattern = self.voice_patterns[user_correction]
                # Increase confidence for this pattern
                pattern.confidence_scores.append(0.9)  # High confidence for user correction
            
            logger.info(f"Learned from correction: {original_suggestion} -> {user_correction}")
            
        except Exception as e:
            logger.error(f"Error learning from user correction: {e}")
    
    def get_speaker_statistics(self) -> Dict[str, Any]:
        """Get statistics about learned speakers."""
        try:
            db_stats = self.db_service.get_speaker_statistics()
            
            # Add voice pattern statistics
            pattern_stats = {
                'total_patterns': len(self.voice_patterns),
                'most_active_speakers': [],
                'average_confidence': 0.0
            }
            
            if self.voice_patterns:
                # Sort by usage count
                sorted_patterns = sorted(
                    self.voice_patterns.values(),
                    key=lambda p: p.usage_count,
                    reverse=True
                )
                
                pattern_stats['most_active_speakers'] = [
                    {
                        'name': pattern.speaker_name,
                        'usage_count': pattern.usage_count,
                        'last_updated': pattern.last_updated.isoformat()
                    }
                    for pattern in sorted_patterns[:5]
                ]
                
                # Calculate average confidence
                all_confidences = []
                for pattern in self.voice_patterns.values():
                    all_confidences.extend(pattern.confidence_scores)
                
                if all_confidences:
                    pattern_stats['average_confidence'] = sum(all_confidences) / len(all_confidences)
            
            return {
                'database_stats': db_stats,
                'pattern_stats': pattern_stats
            }
            
        except Exception as e:
            logger.error(f"Error getting speaker statistics: {e}")
            return {}
    
    def export_speaker_profiles(self, output_path: Path) -> bool:
        """
        Export learned speaker profiles for backup/sharing.
        
        Args:
            output_path: Path to save the exported profiles
            
        Returns:
            True if export was successful
        """
        try:
            export_data = {
                'export_timestamp': datetime.now().isoformat(),
                'voice_patterns': {},
                'metadata': {
                    'total_patterns': len(self.voice_patterns),
                    'export_version': '1.0'
                }
            }
            
            # Export voice patterns
            for name, pattern in self.voice_patterns.items():
                export_data['voice_patterns'][name] = pattern.to_dict()
            
            # Write to file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Exported {len(self.voice_patterns)} speaker profiles to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting speaker profiles: {e}")
            return False
    
    def import_speaker_profiles(self, profile_path: Path) -> bool:
        """
        Import speaker profiles from backup/sharing.
        
        Args:
            profile_path: Path to the profile file to import
            
        Returns:
            True if import was successful
        """
        try:
            if not profile_path.exists():
                logger.error(f"Profile file not found: {profile_path}")
                return False
            
            with open(profile_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            if 'voice_patterns' not in import_data:
                logger.error("Invalid profile file format")
                return False
            
            imported_count = 0
            
            # Import voice patterns
            for name, pattern_data in import_data['voice_patterns'].items():
                try:
                    pattern = VoicePattern.from_dict(pattern_data)
                    
                    # Check if pattern already exists
                    if name in self.voice_patterns:
                        # Merge patterns (keep the one with higher usage count)
                        existing_pattern = self.voice_patterns[name]
                        if pattern.usage_count > existing_pattern.usage_count:
                            self.voice_patterns[name] = pattern
                            self._save_voice_pattern(pattern)
                    else:
                        self.voice_patterns[name] = pattern
                        self._save_voice_pattern(pattern)
                    
                    imported_count += 1
                    
                except Exception as e:
                    logger.warning(f"Error importing pattern for {name}: {e}")
            
            logger.info(f"Imported {imported_count} speaker profiles from {profile_path}")
            return imported_count > 0
            
        except Exception as e:
            logger.error(f"Error importing speaker profiles: {e}")
            return False
    
    def cleanup_old_patterns(self, days_old: int = 90):
        """
        Clean up old, unused voice patterns.
        
        Args:
            days_old: Remove patterns older than this many days with low usage
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            removed_count = 0
            
            patterns_to_remove = []
            
            for name, pattern in self.voice_patterns.items():
                # Remove if old and low usage
                if (pattern.last_updated < cutoff_date and 
                    pattern.usage_count < 3):
                    patterns_to_remove.append(name)
            
            # Remove patterns
            for name in patterns_to_remove:
                del self.voice_patterns[name]
                removed_count += 1
            
            # Also cleanup database
            self.db_service.cleanup_old_data(days_old)
            
            logger.info(f"Cleaned up {removed_count} old voice patterns")
            
        except Exception as e:
            logger.error(f"Error cleaning up old patterns: {e}")


# Global service instance
_learning_service: Optional[SpeakerLearningService] = None


def get_speaker_learning_service() -> SpeakerLearningService:
    """Get the global speaker learning service instance."""
    global _learning_service
    if _learning_service is None:
        _learning_service = SpeakerLearningService()
    return _learning_service
