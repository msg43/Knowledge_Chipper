"""GUI tabs package."""

from .api_keys_tab import APIKeysTab
from .claim_search_tab import ClaimSearchTab
from .extract_tab import ExtractTab  # Claims-first extraction tab
from .introduction_tab import IntroductionTab
from .process_tab import ProcessTab
from .prompts_tab import PromptsTab
from .queue_tab import QueueTab

# REMOVED in v4.0.0: Speaker attribution tab replaced by claims-first architecture
# from .speaker_attribution_tab import SpeakerAttributionTab

from .summarization_tab import SummarizationTab
from .summary_cleanup_tab import SummaryCleanupTab

# Make SyncStatusTab optional (depends on optional 'supabase' package)
try:
    from .sync_status_tab import SyncStatusTab
except Exception:
    SyncStatusTab = None  # type: ignore

# Make CloudUploadsTab optional at import time
try:
    from .cloud_uploads_tab import CloudUploadsTab
except Exception:
    CloudUploadsTab = None  # type: ignore

from .monitor_tab import MonitorTab
from .question_review_tab import QuestionReviewTab
from .transcription_tab import TranscriptionTab

# YouTube tab removed - use Transcription tab for YouTube URLs

__all__ = [
    "IntroductionTab",
    "ProcessTab",
    "ExtractTab",  # Claims-first extraction
    "MonitorTab",
    "TranscriptionTab",
    "SummarizationTab",
    "QueueTab",
    "ClaimSearchTab",
    # "SpeakerAttributionTab",  # REMOVED in v4.0.0
    "SummaryCleanupTab",
    "SyncStatusTab",
    "CloudUploadsTab",
    "APIKeysTab",
    "PromptsTab",
    "QuestionReviewTab",
]
