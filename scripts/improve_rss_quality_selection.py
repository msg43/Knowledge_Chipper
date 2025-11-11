#!/usr/bin/env python3
"""
Improve RSS audio quality selection to prefer lowest quality (like YouTube).
Currently it just takes the first audio enclosure found.
"""

from pathlib import Path

file_path = Path("src/knowledge_system/services/podcast_rss_downloader.py")
content = file_path.read_text()

# Replace the audio enclosure extraction to prefer lowest quality
old_extraction = """            if hasattr(entry, "enclosures") and entry.enclosures:
                for enclosure in entry.enclosures:
                    # Look for audio/* MIME types
                    if enclosure.get("type", "").startswith("audio/"):
                        audio_url = enclosure.get("href") or enclosure.get("url")
                        audio_type = enclosure.get("type")
                        audio_length = enclosure.get("length")
                        break"""

new_extraction = """            if hasattr(entry, "enclosures") and entry.enclosures:
                # Collect all audio enclosures
                audio_enclosures = []
                for enclosure in entry.enclosures:
                    # Look for audio/* MIME types
                    if enclosure.get("type", "").startswith("audio/"):
                        audio_enclosures.append(enclosure)

                # Prefer lowest quality (smallest file) to minimize bandwidth
                # Sort by length (file size) ascending - smallest first
                if audio_enclosures:
                    # Sort by length if available, otherwise use first
                    audio_enclosures_with_length = [
                        e for e in audio_enclosures if e.get("length")
                    ]

                    if audio_enclosures_with_length:
                        # Sort by length (ascending) - smallest file first
                        selected = min(
                            audio_enclosures_with_length,
                            key=lambda e: int(e.get("length", 0))
                        )
                        logger.debug(
                            f"Selected lowest quality audio: "
                            f"{int(selected.get('length', 0)) / 1024 / 1024:.1f} MB "
                            f"({selected.get('type', 'unknown')})"
                        )
                    else:
                        # No length info, just use first audio enclosure
                        selected = audio_enclosures[0]
                        logger.debug(
                            f"Using first audio enclosure (no size info): "
                            f"{selected.get('type', 'unknown')}"
                        )

                    audio_url = selected.get("href") or selected.get("url")
                    audio_type = selected.get("type")
                    audio_length = selected.get("length")"""

content = content.replace(old_extraction, new_extraction)

file_path.write_text(content)

print("✅ Improved RSS audio quality selection")
print("\n📝 Changes:")
print("   • Collects ALL audio enclosures (not just first)")
print("   • Sorts by file size (length) ascending")
print("   • Selects SMALLEST file (lowest quality)")
print("   • Falls back to first if no size info available")
print("   • Logs selected quality and file size")
print("\n💡 Behavior:")
print("   • Before: Used first audio enclosure found")
print("   • After: Prefers smallest/lowest quality (like YouTube worstaudio)")
print(
    "   • Matches YouTube strategy: minimize bandwidth, transcription doesn't need HQ"
)
