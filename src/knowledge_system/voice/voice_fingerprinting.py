"""
Advanced Voice Fingerprinting and Speaker Verification System

This module implements state-of-the-art voice matching and speaker verification
to achieve 97% accuracy on 16kHz mono WAV files.

Features:
- Multi-modal voice feature extraction (MFCC, spectrograms, voice embeddings)
- State-of-the-art speaker verification models (wav2vec2, ECAPA-TDNN)
- Cosine similarity matching with configurable thresholds
- Voice enrollment and verification pipeline
- Persistent voice profile database
"""

import warnings
from pathlib import Path
from typing import Any

import librosa
import numpy as np
import torch
import torch.nn.functional as F
from scipy.spatial.distance import cosine

# Suppress specific warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

try:
    # Try importing transformers for wav2vec2
    from transformers import Wav2Vec2FeatureExtractor, Wav2Vec2Model

    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

try:
    # Try importing speechbrain for ECAPA-TDNN
    from speechbrain.pretrained import EncoderClassifier

    HAS_SPEECHBRAIN = True
except ImportError:
    HAS_SPEECHBRAIN = False

from ..database.speaker_models import (  # noqa: E402
    SpeakerDatabaseService,
    SpeakerVoiceModel,
)
from ..logger import get_logger  # noqa: E402

logger = get_logger(__name__)


class VoiceFeatureExtractor:
    """Extract multiple types of voice features for comprehensive fingerprinting."""

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate

    def extract_mfcc_features(self, audio: np.ndarray, n_mfcc: int = 13) -> np.ndarray:
        """Extract MFCC features from audio."""
        try:
            # Extract MFCCs
            mfccs = librosa.feature.mfcc(
                y=audio, sr=self.sample_rate, n_mfcc=n_mfcc, n_fft=2048, hop_length=512
            )

            # Compute statistics: mean, std, min, max
            mfcc_stats = np.array(
                [
                    np.mean(mfccs, axis=1),  # Mean
                    np.std(mfccs, axis=1),  # Standard deviation
                    np.min(mfccs, axis=1),  # Minimum
                    np.max(mfccs, axis=1),  # Maximum
                ]
            ).flatten()

            return mfcc_stats

        except Exception as e:
            logger.error(f"Error extracting MFCC features: {e}")
            return np.zeros(n_mfcc * 4)  # Return zeros if extraction fails

    def extract_spectral_features(self, audio: np.ndarray) -> np.ndarray:
        """Extract spectral features (centroid, rolloff, zero crossing rate)."""
        try:
            # Spectral centroid
            spectral_centroid = librosa.feature.spectral_centroid(
                y=audio, sr=self.sample_rate
            )

            # Spectral rolloff
            spectral_rolloff = librosa.feature.spectral_rolloff(
                y=audio, sr=self.sample_rate
            )

            # Zero crossing rate
            zcr = librosa.feature.zero_crossing_rate(audio)

            # Compute statistics
            features = np.array(
                [
                    np.mean(spectral_centroid),
                    np.std(spectral_centroid),
                    np.mean(spectral_rolloff),
                    np.std(spectral_rolloff),
                    np.mean(zcr),
                    np.std(zcr),
                ]
            )

            return features

        except Exception as e:
            logger.error(f"Error extracting spectral features: {e}")
            return np.zeros(6)

    def extract_prosodic_features(self, audio: np.ndarray) -> np.ndarray:
        """Extract prosodic features (pitch, tempo, rhythm)."""
        try:
            # Fundamental frequency (pitch)
            f0 = librosa.yin(audio, fmin=50, fmax=400, sr=self.sample_rate)

            # Remove unvoiced frames (set to NaN by librosa.yin)
            voiced_f0 = f0[~np.isnan(f0)]

            if len(voiced_f0) > 0:
                pitch_features = np.array(
                    [
                        np.mean(voiced_f0),
                        np.std(voiced_f0),
                        np.min(voiced_f0),
                        np.max(voiced_f0),
                    ]
                )
            else:
                pitch_features = np.zeros(4)

            # Tempo estimation
            try:
                tempo, _ = librosa.beat.beat_track(y=audio, sr=self.sample_rate)
                # Ensure tempo is a scalar (librosa may return array or scalar)
                if isinstance(tempo, np.ndarray):
                    tempo_value = (
                        float(tempo.item()) if tempo.size == 1 else float(tempo[0])
                    )
                else:
                    tempo_value = float(tempo)
                tempo_features = np.array([tempo_value])
            except Exception:
                tempo_features = np.array([0.0])

            return np.concatenate([pitch_features, tempo_features])

        except Exception as e:
            logger.error(f"Error extracting prosodic features: {e}")
            return np.zeros(5)


class AdvancedVoiceEncoder:
    """State-of-the-art voice encoding using pre-trained models."""

    def __init__(self, device: str = "auto"):
        self.device = self._detect_device(device)
        self.wav2vec2_model = None
        self.wav2vec2_processor = None
        self.ecapa_model = None

        # Check for bundled models in DMG
        self._bundled_models_path = self._detect_bundled_models()

    def _detect_device(self, device: str) -> str:
        """Detect the best available device."""
        if device == "auto":
            if torch.backends.mps.is_available():
                return "mps"
            elif torch.cuda.is_available():
                return "cuda"
            else:
                return "cpu"
        return device

    def _detect_bundled_models(self) -> Path | None:
        """Detect if models are bundled in DMG."""
        import os

        # Check for bundled models environment variable
        if os.environ.get("VOICE_MODELS_BUNDLED") == "true":
            bundled_path = os.environ.get("VOICE_MODELS_CACHE")
            if bundled_path and Path(bundled_path).exists():
                logger.info(f"Found bundled voice models at: {bundled_path}")
                return Path(bundled_path)

        # Check common bundled locations
        possible_paths = [
            # DMG bundle location
            Path(__file__).parent.parent.parent.parent
            / "Contents"
            / "MacOS"
            / ".cache"
            / "knowledge_chipper"
            / "voice_models",
            # Alternative app bundle location
            Path.cwd() / ".cache" / "knowledge_chipper" / "voice_models",
            # Development location
            Path.home() / ".cache" / "knowledge_chipper" / "voice_models",
        ]

        for path in possible_paths:
            if path.exists() and any(path.iterdir()):
                logger.info(f"Found voice models at: {path}")
                return path

        logger.info("No bundled voice models found - will use default cache locations")
        return None

    def _load_wav2vec2(self):
        """Lazy load wav2vec2 model for voice embeddings."""
        if not HAS_TRANSFORMERS:
            logger.warning("🔍 DIAGNOSTIC: Transformers package not installed (HAS_TRANSFORMERS=False)")
            logger.warning("   → wav2vec2 embeddings will NOT be available")
            logger.warning("   → Install with: pip install transformers")
            return False

        try:
            logger.info("🔍 DIAGNOSTIC: Loading wav2vec2 model for voice embeddings...")

            # Use bundled model if available, otherwise download
            model_name = "facebook/wav2vec2-base-960h"

            if self._bundled_models_path:
                bundled_wav2vec2 = (
                    self._bundled_models_path
                    / "wav2vec2"
                    / "models--facebook--wav2vec2-base-960h"
                )
                if bundled_wav2vec2.exists():
                    logger.info("Using bundled wav2vec2 model")
                    # Set HF cache to bundled location
                    import os

                    os.environ["HF_HOME"] = str(self._bundled_models_path / "wav2vec2")

            self.wav2vec2_processor = Wav2Vec2FeatureExtractor.from_pretrained(
                model_name
            )
            self.wav2vec2_model = Wav2Vec2Model.from_pretrained(model_name).to(
                self.device
            )
            self.wav2vec2_model.eval()

            logger.info(f"✅ DIAGNOSTIC: Wav2vec2 model loaded successfully on {self.device}")
            return True

        except Exception as e:
            logger.error(f"❌ DIAGNOSTIC: Failed to load wav2vec2 model: {e}")
            logger.error("   → wav2vec2 embeddings will NOT be available")
            return False

    def _load_ecapa_tdnn(self):
        """Lazy load ECAPA-TDNN model for speaker verification."""
        if not HAS_SPEECHBRAIN:
            logger.warning("🔍 DIAGNOSTIC: SpeechBrain package not installed (HAS_SPEECHBRAIN=False)")
            logger.warning("   → ECAPA-TDNN embeddings will NOT be available")
            logger.warning("   → Install with: pip install speechbrain")
            return False

        try:
            logger.info("🔍 DIAGNOSTIC: Loading ECAPA-TDNN model for speaker verification...")

            # Use bundled model if available
            if self._bundled_models_path:
                bundled_ecapa = (
                    self._bundled_models_path / "speechbrain" / "spkrec-ecapa-voxceleb"
                )
                if bundled_ecapa.exists():
                    logger.info("Using bundled ECAPA-TDNN model")
                    # Set SpeechBrain cache to bundled location
                    import os

                    os.environ["SPEECHBRAIN_CACHE"] = str(
                        self._bundled_models_path / "speechbrain"
                    )

                    self.ecapa_model = EncoderClassifier.from_hparams(
                        source="speechbrain/spkrec-ecapa-voxceleb",
                        savedir=str(bundled_ecapa),
                        run_opts={"device": self.device},
                    )
                else:
                    # Fall back to default download
                    self.ecapa_model = EncoderClassifier.from_hparams(
                        source="speechbrain/spkrec-ecapa-voxceleb",
                        savedir="./pretrained_models/spkrec-ecapa-voxceleb",
                        run_opts={"device": self.device},
                    )
            else:
                # No bundled models, download normally
                self.ecapa_model = EncoderClassifier.from_hparams(
                    source="speechbrain/spkrec-ecapa-voxceleb",
                    savedir="./pretrained_models/spkrec-ecapa-voxceleb",
                    run_opts={"device": self.device},
                )

            logger.info(f"✅ DIAGNOSTIC: ECAPA-TDNN model loaded successfully on {self.device}")
            return True

        except Exception as e:
            logger.error(f"❌ DIAGNOSTIC: Failed to load ECAPA-TDNN model: {e}")
            logger.error("   → ECAPA-TDNN embeddings will NOT be available")
            return False

    def extract_wav2vec2_embeddings(
        self, audio: np.ndarray, sample_rate: int = 16000
    ) -> np.ndarray | None:
        """Extract wav2vec2 voice embeddings."""
        if self.wav2vec2_model is None and not self._load_wav2vec2():
            return None

        try:
            # Resample if needed
            if sample_rate != 16000:
                audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=16000)

            # Process audio
            inputs = self.wav2vec2_processor(
                audio, sampling_rate=16000, return_tensors="pt", padding=True
            )

            # Move to device
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # Extract embeddings
            with torch.no_grad():
                outputs = self.wav2vec2_model(**inputs)
                # Use the last hidden state and average pool
                embeddings = outputs.last_hidden_state.mean(dim=1)  # Shape: (1, 768)

            return embeddings.cpu().numpy().flatten()

        except Exception as e:
            logger.error(f"Error extracting wav2vec2 embeddings: {e}")
            return None

    def extract_ecapa_embeddings(
        self, audio: np.ndarray, sample_rate: int = 16000
    ) -> np.ndarray | None:
        """Extract ECAPA-TDNN speaker embeddings."""
        if self.ecapa_model is None and not self._load_ecapa_tdnn():
            return None

        try:
            # Convert to tensor and resample if needed
            audio_tensor = torch.tensor(audio).float()

            if sample_rate != 16000:
                # Simple resampling - for production, use proper resampling
                target_length = int(len(audio) * 16000 / sample_rate)
                audio_tensor = F.interpolate(
                    audio_tensor.unsqueeze(0).unsqueeze(0),
                    size=target_length,
                    mode="linear",
                ).squeeze()

            # Extract embeddings
            embeddings = self.ecapa_model.encode_batch(audio_tensor.unsqueeze(0))

            return embeddings.cpu().numpy().flatten()

        except Exception as e:
            logger.error(f"Error extracting ECAPA embeddings: {e}")
            return None


class VoiceFingerprintProcessor:
    """Main voice fingerprinting processor combining multiple feature types."""

    def __init__(self, sample_rate: int = 16000, device: str = "auto"):
        self.sample_rate = sample_rate
        self.feature_extractor = VoiceFeatureExtractor(sample_rate)
        self.voice_encoder = AdvancedVoiceEncoder(device)
        self.db_service = SpeakerDatabaseService()

    def extract_voice_fingerprint(
        self, audio: np.ndarray, sample_rate: int = None
    ) -> dict[str, Any]:
        """Extract comprehensive voice fingerprint from audio."""
        if sample_rate is None:
            sample_rate = self.sample_rate

        logger.info("Extracting comprehensive voice fingerprint...")

        fingerprint = {}

        # Traditional audio features
        try:
            fingerprint["mfcc"] = self.feature_extractor.extract_mfcc_features(
                audio
            ).tolist()
            fingerprint["spectral"] = self.feature_extractor.extract_spectral_features(
                audio
            ).tolist()
            fingerprint["prosodic"] = self.feature_extractor.extract_prosodic_features(
                audio
            ).tolist()
        except Exception as e:
            logger.error(f"Error extracting traditional features: {e}")
            fingerprint["mfcc"] = []
            fingerprint["spectral"] = []
            fingerprint["prosodic"] = []

        # Deep learning embeddings
        wav2vec2_emb = self.voice_encoder.extract_wav2vec2_embeddings(
            audio, sample_rate
        )
        if wav2vec2_emb is not None:
            fingerprint["wav2vec2"] = wav2vec2_emb.tolist()
        else:
            fingerprint["wav2vec2"] = []

        ecapa_emb = self.voice_encoder.extract_ecapa_embeddings(audio, sample_rate)
        if ecapa_emb is not None:
            fingerprint["ecapa"] = ecapa_emb.tolist()
        else:
            fingerprint["ecapa"] = []

        # Metadata
        fingerprint["sample_rate"] = sample_rate
        fingerprint["duration"] = len(audio) / sample_rate
        fingerprint["feature_version"] = "1.0"

        # 🔍 Debug: Log which features were successfully extracted
        features_extracted = []
        features_empty = []
        for key in ["mfcc", "spectral", "prosodic", "wav2vec2", "ecapa"]:
            if key in fingerprint:
                if fingerprint[key] and len(fingerprint[key]) > 0:
                    features_extracted.append(key)
                else:
                    features_empty.append(key)

        logger.info(
            f"🔍 DIAGNOSTIC: Voice fingerprint extracted - Success: [{', '.join(features_extracted)}], Empty: [{', '.join(features_empty)}]"
        )

        # Additional detail for debugging
        if features_empty:
            logger.warning(f"⚠️ DIAGNOSTIC: Missing features will reduce similarity accuracy")
            logger.warning(f"   → Missing: {features_empty}")
            if "wav2vec2" in features_empty or "ecapa" in features_empty:
                logger.warning(f"   → Deep learning models (60% weight) are missing!")
                logger.warning(f"   → Expected similarity scores will be MUCH LOWER (0.4-0.6 instead of 0.8-0.9)")
        return fingerprint

    def calculate_voice_similarity(
        self, fingerprint1: dict[str, Any], fingerprint2: dict[str, Any]
    ) -> float:
        """Calculate similarity between two voice fingerprints."""

        similarities = []
        weights = {
            "mfcc": 0.2,
            "spectral": 0.1,
            "prosodic": 0.1,
            "wav2vec2": 0.3,
            "ecapa": 0.3,
        }

        # 🔍 Debug: Log which features are available
        features_available = []
        features_missing = []

        for feature_type, weight in weights.items():
            if (
                feature_type in fingerprint1
                and feature_type in fingerprint2
                and fingerprint1[feature_type]
                and fingerprint2[feature_type]
            ):
                try:
                    vec1 = np.array(fingerprint1[feature_type])
                    vec2 = np.array(fingerprint2[feature_type])

                    # Ensure same dimensionality
                    if vec1.shape == vec2.shape:
                        # Use cosine similarity
                        similarity = 1 - cosine(vec1, vec2)
                        similarities.append((similarity, weight))
                        features_available.append(f"{feature_type}={similarity:.3f}")
                    else:
                        features_missing.append(f"{feature_type}(shape_mismatch)")

                except Exception as e:
                    logger.warning(f"Error calculating {feature_type} similarity: {e}")
                    features_missing.append(f"{feature_type}(error)")
                    continue
            else:
                features_missing.append(f"{feature_type}(missing)")

        # 🔍 Debug: Log feature analysis
        logger.info(
            f"🔍 DIAGNOSTIC: Voice similarity features - Available: [{', '.join(features_available)}], Missing: [{', '.join(features_missing)}]"
        )

        if not similarities:
            logger.warning("⚠️ DIAGNOSTIC: No valid features for voice similarity calculation!")
            logger.warning("   → This means fingerprints have no overlapping features")
            return 0.0

        # Weighted average similarity
        total_weight = sum(weight for _, weight in similarities)
        if total_weight == 0:
            return 0.0

        weighted_similarity = (
            sum(sim * weight for sim, weight in similarities) / total_weight
        )

        final_score = max(0.0, min(1.0, weighted_similarity))  # Clamp to [0, 1]
        logger.info(
            f"🔍 DIAGNOSTIC: Voice similarity calculated: {final_score:.3f} from {len(similarities)} features (total weight: {total_weight:.2f})"
        )

        # Diagnostic: Explain if score seems low
        if final_score < 0.7 and len(similarities) < 5:
            logger.warning(f"⚠️ DIAGNOSTIC: Low similarity score ({final_score:.3f}) with incomplete features")
            logger.warning(f"   → Only {len(similarities)}/5 features available (weight: {total_weight:.2f}/1.00)")
            logger.warning(f"   → This may cause false negatives (same speaker not merged)")

        return final_score

    def enroll_speaker(
        self, speaker_name: str, audio_segments: list[np.ndarray]
    ) -> bool:
        """Enroll a speaker by creating a voice profile from multiple audio segments."""
        logger.info(
            f"Enrolling speaker '{speaker_name}' with {len(audio_segments)} segments"
        )

        # Extract fingerprints from all segments
        fingerprints = []
        for i, audio in enumerate(audio_segments):
            try:
                fingerprint = self.extract_voice_fingerprint(audio)
                fingerprints.append(fingerprint)
                logger.info(f"Processed enrollment segment {i+1}/{len(audio_segments)}")
            except Exception as e:
                logger.error(f"Error processing enrollment segment {i}: {e}")
                continue

        if not fingerprints:
            logger.error("No valid fingerprints extracted for enrollment")
            return False

        # Create averaged/representative fingerprint
        avg_fingerprint = self._average_fingerprints(fingerprints)

        # Store in database
        try:
            voice_data = SpeakerVoiceModel(
                name=speaker_name,
                voice_fingerprint=avg_fingerprint,
                confidence_threshold=0.8,  # High threshold for 97% accuracy
            )

            result = self.db_service.create_speaker_voice(voice_data)
            if result:
                logger.info(f"Successfully enrolled speaker '{speaker_name}'")
                return True
            else:
                logger.error(f"Failed to store voice profile for '{speaker_name}'")
                return False

        except Exception as e:
            logger.error(f"Error enrolling speaker: {e}")
            return False

    def verify_speaker(
        self, audio: np.ndarray, candidate_name: str, threshold: float = 0.85
    ) -> tuple[bool, float]:
        """Verify if audio matches a known speaker."""
        try:
            # Extract fingerprint from audio
            test_fingerprint = self.extract_voice_fingerprint(audio)

            # Get stored voice profile
            stored_voice = self.db_service.get_speaker_voice_by_name(candidate_name)
            if not stored_voice:
                logger.warning(f"No voice profile found for '{candidate_name}'")
                return False, 0.0

            # Calculate similarity
            similarity = self.calculate_voice_similarity(
                test_fingerprint, stored_voice.fingerprint_data
            )

            # Apply verification threshold
            is_match = similarity >= threshold

            logger.info(
                f"Speaker verification for '{candidate_name}': {similarity:.3f} (threshold: {threshold})"
            )
            return is_match, similarity

        except Exception as e:
            logger.error(f"Error during speaker verification: {e}")
            return False, 0.0

    def identify_speaker(
        self, audio: np.ndarray, threshold: float = 0.85
    ) -> tuple[str, float] | None:
        """
        Identify the most likely speaker from enrolled profiles.

        Args:
            audio: Audio segment to identify
            threshold: Minimum similarity threshold for positive identification

        Returns:
            Tuple of (speaker_name, confidence) or None if no match found
        """
        try:
            # Extract fingerprint from audio
            test_fingerprint = self.extract_voice_fingerprint(audio)

            # Get all voice profiles and find matches
            matches = self.db_service.find_matching_voices(test_fingerprint, threshold)

            if not matches:
                logger.debug(
                    f"No matching voice profiles found (threshold: {threshold})"
                )
                return None

            # Return the best match
            best_match_voice, best_similarity = matches[0]

            logger.info(
                f"Identified speaker as '{best_match_voice.name}' with confidence {best_similarity:.3f}"
            )
            return best_match_voice.name, best_similarity

        except Exception as e:
            logger.error(f"Error during speaker identification: {e}")
            return None

    def accumulate_speaker_profile(
        self,
        existing_profile: dict[str, Any] | None,
        new_fingerprint: dict[str, Any],
        existing_sample_count: int = 0,
        weight: float = 1.0,
    ) -> dict[str, Any]:
        """
        Combine existing profile with new fingerprint using weighted average.
        
        More samples = more reliable profile. Uses incremental averaging formula:
        new_avg = (old_avg * old_count + new_value * weight) / (old_count + weight)
        
        Args:
            existing_profile: Existing averaged fingerprint (None for first sample)
            new_fingerprint: New fingerprint to incorporate
            existing_sample_count: Number of samples in existing profile
            weight: Weight for new fingerprint (default 1.0)
            
        Returns:
            Updated averaged fingerprint
        """
        if not new_fingerprint:
            return existing_profile or {}
            
        if not existing_profile or existing_sample_count == 0:
            # First sample - just return the new fingerprint
            return new_fingerprint.copy()
        
        accumulated = {}
        feature_types = ["mfcc", "spectral", "prosodic", "wav2vec2", "ecapa"]
        
        for feature_type in feature_types:
            existing_feat = existing_profile.get(feature_type)
            new_feat = new_fingerprint.get(feature_type)
            
            if new_feat and len(new_feat) > 0:
                new_array = np.array(new_feat)
                
                if existing_feat and len(existing_feat) > 0:
                    existing_array = np.array(existing_feat)
                    
                    # Check shape compatibility
                    if existing_array.shape == new_array.shape:
                        # Incremental weighted average
                        total_weight = existing_sample_count + weight
                        accumulated_array = (
                            existing_array * existing_sample_count + new_array * weight
                        ) / total_weight
                        accumulated[feature_type] = accumulated_array.tolist()
                    else:
                        # Shape mismatch - use new fingerprint for this feature
                        logger.warning(
                            f"Shape mismatch for {feature_type}: existing {existing_array.shape} vs new {new_array.shape}"
                        )
                        accumulated[feature_type] = new_feat
                else:
                    # No existing feature - use new one
                    accumulated[feature_type] = new_feat
            elif existing_feat:
                # Keep existing feature if new one is missing
                accumulated[feature_type] = existing_feat
        
        # Copy metadata
        accumulated["sample_rate"] = new_fingerprint.get("sample_rate", 16000)
        accumulated["feature_version"] = new_fingerprint.get("feature_version", "1.0")
        accumulated["accumulated_samples"] = existing_sample_count + 1
        
        return accumulated

    def get_channel_speaker_profiles(
        self, channel_id: str
    ) -> dict[str, dict[str, Any]]:
        """
        Get all speaker profiles for a channel from the database.
        
        Args:
            channel_id: YouTube channel ID
            
        Returns:
            Dictionary mapping speaker names to their fingerprint data
        """
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            
            from ..database.models import PersistentSpeakerProfile
            from ..utils.macos_paths import get_application_support_dir
            
            # Get database path
            db_path = get_application_support_dir() / "knowledge_system.db"
            engine = create_engine(f"sqlite:///{db_path}")
            Session = sessionmaker(bind=engine)
            
            with Session() as session:
                profiles = (
                    session.query(PersistentSpeakerProfile)
                    .filter_by(channel_id=channel_id)
                    .all()
                )
                
                result = {}
                for profile in profiles:
                    if profile.fingerprint_data:
                        result[profile.name] = {
                            "fingerprint": profile.fingerprint_data,
                            "sample_count": profile.sample_count,
                            "confidence": profile.confidence_score,
                            "has_wav2vec2": profile.has_wav2vec2,
                            "has_ecapa": profile.has_ecapa,
                        }
                        
                return result
                
        except Exception as e:
            logger.warning(f"Error loading channel speaker profiles: {e}")
            return {}

    def save_speaker_profile(
        self,
        name: str,
        fingerprint: dict[str, Any],
        channel_id: str | None = None,
        channel_name: str | None = None,
        source_id: str | None = None,
        duration_seconds: float = 0.0,
    ) -> bool:
        """
        Save or update a speaker profile in the database.
        
        If a profile already exists for this speaker+channel, accumulates the
        new fingerprint with the existing one using weighted averaging.
        
        Args:
            name: Speaker name
            fingerprint: Voice fingerprint dictionary
            channel_id: YouTube channel ID (optional)
            channel_name: Human-readable channel name (optional)
            source_id: Source episode ID that contributed this sample
            duration_seconds: Duration of audio used for this fingerprint
            
        Returns:
            True if saved successfully
        """
        try:
            from datetime import datetime
            
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            
            from ..database.models import Base, PersistentSpeakerProfile
            from ..utils.macos_paths import get_application_support_dir
            
            # Get database path
            db_path = get_application_support_dir() / "knowledge_system.db"
            engine = create_engine(f"sqlite:///{db_path}")
            
            # Ensure table exists
            Base.metadata.create_all(engine, tables=[PersistentSpeakerProfile.__table__])
            
            Session = sessionmaker(bind=engine)
            
            with Session() as session:
                # Look for existing profile
                query = session.query(PersistentSpeakerProfile).filter_by(name=name)
                if channel_id:
                    query = query.filter_by(channel_id=channel_id)
                else:
                    query = query.filter(PersistentSpeakerProfile.channel_id.is_(None))
                    
                existing = query.first()
                
                if existing:
                    # Accumulate with existing profile
                    accumulated = self.accumulate_speaker_profile(
                        existing.fingerprint_data,
                        fingerprint,
                        existing.sample_count,
                    )
                    
                    existing.fingerprint_data = accumulated
                    existing.sample_count += 1
                    existing.total_duration_seconds += duration_seconds
                    existing.updated_at = datetime.utcnow()
                    
                    # Update feature availability
                    existing.has_wav2vec2 = bool(accumulated.get("wav2vec2"))
                    existing.has_ecapa = bool(accumulated.get("ecapa"))
                    
                    # Update confidence based on sample count and features
                    existing.confidence_score = self._calculate_profile_confidence(
                        existing.sample_count,
                        existing.has_wav2vec2,
                        existing.has_ecapa,
                    )
                    
                    # Add source episode
                    if source_id:
                        existing.add_source_episode(source_id)
                    
                    logger.info(
                        f"Updated speaker profile '{name}' (samples: {existing.sample_count}, "
                        f"confidence: {existing.confidence_score:.2f})"
                    )
                else:
                    # Create new profile
                    has_wav2vec2 = bool(fingerprint.get("wav2vec2"))
                    has_ecapa = bool(fingerprint.get("ecapa"))
                    confidence = self._calculate_profile_confidence(1, has_wav2vec2, has_ecapa)
                    
                    new_profile = PersistentSpeakerProfile(
                        name=name,
                        channel_id=channel_id,
                        channel_name=channel_name,
                        sample_count=1,
                        total_duration_seconds=duration_seconds,
                        confidence_score=confidence,
                        has_wav2vec2=has_wav2vec2,
                        has_ecapa=has_ecapa,
                    )
                    new_profile.fingerprint_data = fingerprint
                    
                    if source_id:
                        new_profile.source_episode_list = [source_id]
                    
                    session.add(new_profile)
                    logger.info(
                        f"Created new speaker profile '{name}' for channel '{channel_id}'"
                    )
                
                session.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error saving speaker profile: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False

    def _calculate_profile_confidence(
        self,
        sample_count: int,
        has_wav2vec2: bool,
        has_ecapa: bool,
    ) -> float:
        """
        Calculate confidence score for a speaker profile.
        
        Confidence increases with:
        - More samples (diminishing returns after 10)
        - Availability of deep learning features (wav2vec2, ecapa)
        
        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Base confidence from sample count (0.3 to 0.7)
        # Logarithmic scaling: 1 sample = 0.3, 10 samples = 0.7
        sample_confidence = 0.3 + 0.4 * min(1.0, np.log10(sample_count + 1) / np.log10(11))
        
        # Feature bonus (up to 0.3)
        feature_bonus = 0.0
        if has_wav2vec2:
            feature_bonus += 0.15
        if has_ecapa:
            feature_bonus += 0.15
            
        return min(1.0, sample_confidence + feature_bonus)

    def get_or_create_channel_profile(
        self,
        channel_id: str,
        speaker_name: str,
        audio_segments: list[np.ndarray],
        channel_name: str | None = None,
        source_id: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Get existing profile for channel speaker or create from audio.
        
        If a profile exists with sufficient confidence, returns it directly.
        Otherwise, extracts fingerprint from provided audio and saves/updates.
        
        Args:
            channel_id: YouTube channel ID
            speaker_name: Speaker name
            audio_segments: List of audio arrays (16kHz mono) for fingerprinting
            channel_name: Human-readable channel name
            source_id: Source episode ID
            
        Returns:
            Speaker fingerprint dictionary, or None if extraction failed
        """
        # Try to get existing profile
        existing_profiles = self.get_channel_speaker_profiles(channel_id)
        
        if speaker_name in existing_profiles:
            profile_data = existing_profiles[speaker_name]
            
            # If high confidence, return existing profile
            if profile_data["confidence"] >= 0.7:
                logger.info(
                    f"Using existing profile for '{speaker_name}' "
                    f"(confidence: {profile_data['confidence']:.2f}, "
                    f"samples: {profile_data['sample_count']})"
                )
                return profile_data["fingerprint"]
        
        # Extract fingerprint from audio segments
        if not audio_segments:
            logger.warning(f"No audio segments provided for '{speaker_name}'")
            return existing_profiles.get(speaker_name, {}).get("fingerprint")
        
        # Concatenate audio segments (up to 60 seconds for profile)
        max_samples = 60 * self.sample_rate  # 60 seconds
        concatenated = []
        total_samples = 0
        
        for segment in audio_segments:
            if total_samples >= max_samples:
                break
            remaining = max_samples - total_samples
            concatenated.append(segment[:remaining])
            total_samples += len(segment[:remaining])
        
        if not concatenated:
            return existing_profiles.get(speaker_name, {}).get("fingerprint")
            
        audio = np.concatenate(concatenated)
        duration = len(audio) / self.sample_rate
        
        # Extract fingerprint
        fingerprint = self.extract_voice_fingerprint(audio)
        
        if not fingerprint:
            logger.warning(f"Failed to extract fingerprint for '{speaker_name}'")
            return existing_profiles.get(speaker_name, {}).get("fingerprint")
        
        # Save/update profile
        self.save_speaker_profile(
            name=speaker_name,
            fingerprint=fingerprint,
            channel_id=channel_id,
            channel_name=channel_name,
            source_id=source_id,
            duration_seconds=duration,
        )
        
        # Return the (possibly accumulated) profile
        updated_profiles = self.get_channel_speaker_profiles(channel_id)
        if speaker_name in updated_profiles:
            return updated_profiles[speaker_name]["fingerprint"]
            
        return fingerprint

    def update_profiles_from_stable_regions(
        self,
        audio: np.ndarray,
        words: list[dict],
        channel_id: str | None = None,
        channel_name: str | None = None,
        source_id: str | None = None,
        min_stable_duration: float = 2.0,
    ) -> dict[str, dict]:
        """
        Update persistent speaker profiles using only stable regions from DTW timestamps.
        
        This is the recommended method for updating profiles after word-driven alignment.
        It ensures that fingerprints are extracted only from clean, single-speaker regions
        where the speaker label has been stable for at least `min_stable_duration` seconds.
        
        This prevents profile contamination from:
        - Transition zones between speakers
        - Short interjections that may be misattributed
        - Overlapping speech regions
        
        Args:
            audio: Full audio waveform (16kHz mono)
            words: List of word dictionaries with DTW timestamps and speaker labels
                   (from pywhispercpp + pyannote-whisper alignment)
            channel_id: YouTube channel ID for persistent storage
            channel_name: Human-readable channel name
            source_id: Source episode ID for tracking
            min_stable_duration: Minimum seconds of stable speech for fingerprinting
            
        Returns:
            Dictionary mapping speaker IDs to their updated fingerprints
        """
        # Import the stable region functions
        # (They're in this same module, at the module level)
        stable_regions = find_stable_regions(words, min_duration=min_stable_duration)
        
        if not stable_regions:
            logger.info("No stable regions found for profile update")
            return {}
        
        # Extract fingerprints from stable regions
        speaker_fingerprints = extract_fingerprints_from_stable_regions(
            audio=audio,
            stable_regions=stable_regions,
            sample_rate=self.sample_rate,
            voice_processor=self,
        )
        
        if not speaker_fingerprints:
            logger.info("No fingerprints extracted from stable regions")
            return {}
        
        # Update persistent profiles if channel_id provided
        if channel_id:
            for speaker_id, fingerprint in speaker_fingerprints.items():
                # Calculate duration from stable regions for this speaker
                speaker_duration = sum(
                    r["duration"] for r in stable_regions 
                    if r["speaker"] == speaker_id
                )
                
                # Save/update the profile
                self.save_speaker_profile(
                    name=speaker_id,
                    fingerprint=fingerprint,
                    channel_id=channel_id,
                    channel_name=channel_name,
                    source_id=source_id,
                    duration_seconds=speaker_duration,
                )
                
                logger.info(
                    f"Updated persistent profile for '{speaker_id}' from "
                    f"{speaker_duration:.1f}s of stable regions"
                )
        
        return speaker_fingerprints

    def _average_fingerprints(
        self, fingerprints: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Average multiple fingerprints to create a representative profile."""
        if not fingerprints:
            return {}

        # Start with the first fingerprint
        avg_fingerprint = fingerprints[0].copy()

        # Average numerical features
        for feature_type in ["mfcc", "spectral", "prosodic", "wav2vec2", "ecapa"]:
            if feature_type in avg_fingerprint and avg_fingerprint[feature_type]:
                # Collect all vectors for this feature type
                vectors = []
                for fp in fingerprints:
                    if feature_type in fp and fp[feature_type]:
                        vectors.append(np.array(fp[feature_type]))

                if vectors:
                    # Average the vectors
                    avg_vector = np.mean(vectors, axis=0)
                    avg_fingerprint[feature_type] = avg_vector.tolist()

        return avg_fingerprint


def load_audio_for_voice_processing(
    file_path: Path, target_sample_rate: int = 16000
) -> np.ndarray:
    """Load audio file optimized for voice processing."""
    try:
        # Load audio with librosa
        audio, sr = librosa.load(str(file_path), sr=target_sample_rate, mono=True)

        # Normalize audio
        audio = librosa.util.normalize(audio)

        return audio

    except Exception as e:
        logger.error(f"Error loading audio file {file_path}: {e}")
        raise


def find_stable_regions(words: list[dict], min_duration: float = 2.0) -> list[dict]:
    """
    Find regions where speaker label is stable for reliable fingerprinting.
    
    Only stable regions (where the same speaker talks continuously for at least
    min_duration seconds) should be used to build/update speaker profiles.
    This ensures fingerprints are extracted from clean, single-speaker audio
    rather than transition zones where diarization may be uncertain.
    
    This function is part of the word-driven alignment approach, working with
    DTW word-level timestamps from pywhispercpp.
    
    Args:
        words: List of word dictionaries with keys:
            - word: str - the transcribed word
            - start: float - start time in seconds
            - end: float - end time in seconds
            - speaker: str - assigned speaker ID
        min_duration: Minimum duration in seconds for a region to be considered stable
        
    Returns:
        List of stable region dictionaries with keys:
            - speaker: str - the speaker ID
            - start: float - region start time in seconds
            - end: float - region end time in seconds
            - duration: float - region duration in seconds
            - word_count: int - number of words in the region
    """
    stable_regions = []
    current_speaker = None
    region_start = None
    region_word_count = 0
    
    for word in words:
        word_speaker = word.get("speaker")
        word_start = word.get("start", 0)
        
        if word_speaker != current_speaker:
            # Speaker changed - check if previous region was stable
            if region_start is not None and current_speaker is not None:
                duration = word_start - region_start
                if duration >= min_duration:
                    stable_regions.append({
                        "speaker": current_speaker,
                        "start": region_start,
                        "end": word_start,
                        "duration": duration,
                        "word_count": region_word_count,
                    })
            # Start new region
            current_speaker = word_speaker
            region_start = word_start
            region_word_count = 1
        else:
            region_word_count += 1
    
    # Don't forget the last region
    if words and region_start is not None and current_speaker is not None:
        last_word = words[-1]
        duration = last_word.get("end", last_word.get("start", 0)) - region_start
        if duration >= min_duration:
            stable_regions.append({
                "speaker": current_speaker,
                "start": region_start,
                "end": last_word.get("end", last_word.get("start", 0)),
                "duration": duration,
                "word_count": region_word_count,
            })
    
    logger.info(f"Found {len(stable_regions)} stable regions (min {min_duration}s duration)")
    return stable_regions


def extract_fingerprints_from_stable_regions(
    audio: np.ndarray,
    stable_regions: list[dict],
    sample_rate: int = 16000,
    voice_processor: VoiceFingerprintProcessor | None = None,
) -> dict[str, dict]:
    """
    Extract voice fingerprints only from stable speaker regions.
    
    This function extracts fingerprints from audio segments where the speaker
    label is known to be stable (from find_stable_regions), ensuring that
    the fingerprints represent clean, single-speaker audio.
    
    Used for building and updating persistent speaker profiles with accurate
    DTW-based word timestamps.
    
    Args:
        audio: Full audio waveform as numpy array
        stable_regions: List of stable regions from find_stable_regions()
        sample_rate: Audio sample rate in Hz
        voice_processor: Optional VoiceFingerprintProcessor instance
            (created if not provided)
            
    Returns:
        Dictionary mapping speaker IDs to their accumulated voice fingerprints
    """
    if voice_processor is None:
        voice_processor = VoiceFingerprintProcessor(sample_rate=sample_rate)
    
    speaker_fingerprints: dict[str, dict] = {}
    
    for region in stable_regions:
        speaker = region["speaker"]
        if not speaker:
            continue
            
        start_sample = int(region["start"] * sample_rate)
        end_sample = int(region["end"] * sample_rate)
        
        # Bounds checking
        if start_sample < 0:
            start_sample = 0
        if end_sample > len(audio):
            end_sample = len(audio)
        if start_sample >= end_sample:
            continue
        
        # Extract audio segment
        audio_segment = audio[start_sample:end_sample]
        
        # Skip very quiet segments
        if np.max(np.abs(audio_segment)) < 0.01:
            logger.debug(f"Skipping quiet region for {speaker} at {region['start']:.1f}s")
            continue
        
        try:
            # Extract fingerprint from this stable region
            fingerprint = voice_processor.extract_voice_fingerprint(audio_segment)
            
            if fingerprint:
                if speaker not in speaker_fingerprints:
                    speaker_fingerprints[speaker] = fingerprint
                    logger.debug(
                        f"Created fingerprint for {speaker} from {region['duration']:.1f}s region"
                    )
                else:
                    # Accumulate fingerprint (weighted average)
                    existing = speaker_fingerprints[speaker]
                    speaker_fingerprints[speaker] = voice_processor.accumulate_fingerprint(
                        existing, fingerprint
                    )
                    logger.debug(
                        f"Accumulated fingerprint for {speaker} from {region['duration']:.1f}s region"
                    )
        except Exception as e:
            logger.warning(f"Failed to extract fingerprint for {speaker}: {e}")
            continue
    
    logger.info(
        f"Extracted fingerprints for {len(speaker_fingerprints)} speakers "
        f"from {len(stable_regions)} stable regions"
    )
    return speaker_fingerprints


# Factory function for easy integration
def create_voice_fingerprint_processor(
    sample_rate: int = 16000, device: str = "auto"
) -> VoiceFingerprintProcessor:
    """Factory function to create a voice fingerprint processor."""
    return VoiceFingerprintProcessor(sample_rate=sample_rate, device=device)
