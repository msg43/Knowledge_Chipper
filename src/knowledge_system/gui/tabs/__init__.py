"""GUI tabs package."""

from .process_tab import ProcessTab
from .watcher_tab import WatcherTab
from .youtube_tab import YouTubeTab
from .transcription_tab import TranscriptionTab
from .summarization_tab import SummarizationTab
from .api_keys_tab import APIKeysTab

__all__ = [
    'ProcessTab', 
    'WatcherTab',
    'YouTubeTab',
    'TranscriptionTab',
    'SummarizationTab',
    'APIKeysTab'
] 