#!/usr/bin/env python3
"""
Add progress indicators and timeout to podcast RSS downloader.
"""

from pathlib import Path

file_path = Path("src/knowledge_system/services/podcast_rss_downloader.py")
content = file_path.read_text()

# Add tqdm import at the top (after other imports)
old_imports = """import requests

from ..database.service import DatabaseService
from ..logger import get_logger"""

new_imports = """import requests
from tqdm import tqdm

from ..database.service import DatabaseService
from ..logger import get_logger"""

content = content.replace(old_imports, new_imports)

# Add progress indicator to the matching loop
old_matching = """        # Match episodes to YouTube videos
        matched_episodes = []
        for episode in episodes:
            for youtube_source_id, youtube_url in target_source_ids.items():
                is_match, confidence, method = self._match_episode_to_youtube(
                    episode, youtube_source_id, youtube_url
                )
                if is_match:
                    matched_episodes.append(
                        (episode, youtube_source_id, youtube_url, confidence, method)
                    )
                    logger.info(
                        f"✅ Matched episode: {episode['title'][:50]}... "
                        f"(confidence={confidence:.2f}, method={method})"
                    )
                    break"""

new_matching = """        # Match episodes to YouTube videos
        matched_episodes = []
        logger.info(f"🔍 Matching {len(episodes)} episodes against {len(target_source_ids)} target(s)...")

        # Use progress bar for terminal feedback
        with tqdm(total=len(episodes), desc="Matching episodes", unit="ep", disable=None) as pbar:
            for episode in episodes:
                for youtube_source_id, youtube_url in target_source_ids.items():
                    is_match, confidence, method = self._match_episode_to_youtube(
                        episode, youtube_source_id, youtube_url
                    )
                    if is_match:
                        matched_episodes.append(
                            (episode, youtube_source_id, youtube_url, confidence, method)
                        )
                        logger.info(
                            f"✅ Matched episode: {episode['title'][:50]}... "
                            f"(confidence={confidence:.2f}, method={method})"
                        )
                        pbar.set_postfix({"matches": len(matched_episodes)})
                        break
                pbar.update(1)"""

content = content.replace(old_matching, new_matching)

# Add progress indicator to download loop
old_download = """        # Download matched episodes
        downloaded_files = []
        for (
            episode,
            youtube_source_id,
            youtube_url,
            confidence,
            method,
        ) in matched_episodes:
            try:
                audio_file, podcast_source_id = self._download_episode(
                    episode, rss_url, output_dir
                )"""

new_download = """        # Download matched episodes
        downloaded_files = []
        logger.info(f"📥 Downloading {len(matched_episodes)} matched episode(s)...")

        for idx, (
            episode,
            youtube_source_id,
            youtube_url,
            confidence,
            method,
        ) in enumerate(matched_episodes, 1):
            try:
                logger.info(f"[{idx}/{len(matched_episodes)}] Downloading: {episode['title'][:50]}...")
                audio_file, podcast_source_id = self._download_episode(
                    episode, rss_url, output_dir
                )"""

content = content.replace(old_download, new_download)

# Add timeout to feed parsing
old_timeout = """            logger.debug(f"Fetching podcast feed: {rss_url}")
            response = requests.get(rss_url, headers=headers, timeout=30)
            response.raise_for_status()"""

new_timeout = """            logger.info(f"📡 Fetching podcast feed (timeout: 30s)...")
            response = requests.get(rss_url, headers=headers, timeout=30)
            response.raise_for_status()
            logger.info(f"✅ Feed fetched successfully ({len(response.content)} bytes)")"""

content = content.replace(old_timeout, new_timeout)

file_path.write_text(content)

print("✅ Added progress indicators to podcast_rss_downloader.py")
print("\n📝 Changes:")
print("   • Added tqdm import for progress bars")
print("   • Added progress bar to episode matching loop")
print("   • Added counter to download loop")
print("   • Enhanced logging for feed fetching")
print("   • Existing 30s timeout already in place")
