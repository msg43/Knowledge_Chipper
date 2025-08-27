"""GUI tabs package."""

from .api_keys_tab import APIKeysTab
from .claim_search_tab import ClaimSearchTab
from .introduction_tab import IntroductionTab
from .process_tab import ProcessTab
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

from .transcription_tab import TranscriptionTab
from .watcher_tab import WatcherTab
from .youtube_tab import YouTubeTab

__all__ = [
	"IntroductionTab",
	"ProcessTab",
	"WatcherTab",
	"YouTubeTab",
	"TranscriptionTab",
	"SummarizationTab",
	"ClaimSearchTab",
	"SpeakerAttributionTab",
	"SummaryCleanupTab",
	"SyncStatusTab",
	"CloudUploadsTab",
	"APIKeysTab",
]
