"""GUI tabs package."""

from .api_keys_tab import APIKeysTab
from .claim_search_tab import ClaimSearchTab
from .introduction_tab import IntroductionTab
from .process_tab import ProcessTab
from .prompts_tab import PromptsTab
from .speaker_attribution_tab import SpeakerAttributionTab
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
from .transcription_tab import TranscriptionTab
from .youtube_tab import YouTubeTab

__all__ = [
    "IntroductionTab",
    "ProcessTab",
    "MonitorTab",
    "YouTubeTab",
    "TranscriptionTab",
    "SummarizationTab",
    "ClaimSearchTab",
    "SpeakerAttributionTab",
    "SummaryCleanupTab",
    "SyncStatusTab",
    "CloudUploadsTab",
    "APIKeysTab",
    "PromptsTab",
]
