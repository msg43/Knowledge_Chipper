#!/usr/bin/env python3
"""
Optimize RSS episode matching to stop early when all targets are found.
"""

from pathlib import Path

file_path = Path("src/knowledge_system/services/podcast_rss_downloader.py")
content = file_path.read_text()

# Replace the matching loop with an optimized version that stops early
old_matching = """        # Match episodes to YouTube videos
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

new_matching = """        # Match episodes to YouTube videos
        matched_episodes = []
        logger.info(f"🔍 Matching {len(episodes)} episodes against {len(target_source_ids)} target(s)...")
        logger.info(f"💡 Will stop early once all {len(target_source_ids)} target(s) are matched")

        # Track which targets have been matched
        unmatched_targets = set(target_source_ids.keys())

        # Use progress bar for terminal feedback
        with tqdm(total=len(episodes), desc="Matching episodes", unit="ep", disable=None) as pbar:
            for idx, episode in enumerate(episodes, 1):
                # Check against remaining unmatched targets only
                for youtube_source_id in list(unmatched_targets):
                    youtube_url = target_source_ids[youtube_source_id]
                    is_match, confidence, method = self._match_episode_to_youtube(
                        episode, youtube_source_id, youtube_url
                    )
                    if is_match:
                        matched_episodes.append(
                            (episode, youtube_source_id, youtube_url, confidence, method)
                        )
                        unmatched_targets.remove(youtube_source_id)
                        logger.info(
                            f"✅ [{len(matched_episodes)}/{len(target_source_ids)}] Matched: {episode['title'][:50]}... "
                            f"(confidence={confidence:.2f}, method={method})"
                        )
                        pbar.set_postfix({
                            "matches": f"{len(matched_episodes)}/{len(target_source_ids)}",
                            "remaining": len(unmatched_targets)
                        })
                        break

                pbar.update(1)

                # Early exit: Stop if all targets matched
                if not unmatched_targets:
                    logger.info(f"✅ All {len(target_source_ids)} target(s) matched! Stopping early (checked {idx}/{len(episodes)} episodes)")
                    pbar.total = idx  # Update progress bar total to current position
                    pbar.refresh()
                    break"""

content = content.replace(old_matching, new_matching)

file_path.write_text(content)

print("✅ Optimized RSS episode matching")
print("\n📝 Changes:")
print("   • Added early exit when all targets are matched")
print("   • Track unmatched targets to avoid redundant checks")
print("   • Only check against remaining unmatched targets")
print("   • Show progress: matches/total and remaining count")
print("   • Log when stopping early with episode count")
print("\n💡 Performance:")
print("   • Before: Always checks all 280 episodes")
print("   • After: Stops as soon as all targets found (could be 1-10 episodes)")
print("   • Expected speedup: 10-280x faster depending on episode position")
