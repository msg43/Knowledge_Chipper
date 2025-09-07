#!/usr/bin/env python3
"""
Create a comprehensive diarized transcript from YouTube video
"""

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def parse_vtt_to_text(vtt_file_path):
    """Parse VTT file to clean transcript text with timestamps."""
    with open(vtt_file_path, encoding="utf-8") as f:
        content = f.read()

    # Extract timestamp and text pairs
    segments = []
    lines = content.split("\n")

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Look for timestamp line
        if "-->" in line:
            timestamp_match = re.match(
                r"(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})", line
            )
            if timestamp_match:
                start_time = timestamp_match.group(1)
                end_time = timestamp_match.group(2)

                # Get the text on next lines
                i += 1
                text_lines = []
                while i < len(lines) and lines[i].strip() and "-->" not in lines[i]:
                    text_line = lines[i].strip()
                    if text_line:
                        # Clean up the text (remove timing markers)
                        cleaned_text = re.sub(
                            r"<\d{2}:\d{2}:\d{2}\.\d{3}><c>", " ", text_line
                        )
                        cleaned_text = re.sub(r"</c>", "", cleaned_text)
                        cleaned_text = re.sub(
                            r"align:start position:\d+%", "", cleaned_text
                        )
                        text_lines.append(cleaned_text)
                    i += 1

                if text_lines:
                    full_text = " ".join(text_lines).strip()
                    if full_text:
                        segments.append(
                            {"start": start_time, "end": end_time, "text": full_text}
                        )
                continue
        i += 1

    return segments


def create_markdown_transcript(
    title,
    uploader,
    duration,
    upload_date,
    description,
    view_count,
    url,
    segments,
    output_file,
):
    """Create a comprehensive markdown file with metadata and transcript."""

    # Parse duration (seconds to MM:SS)
    duration_int = int(float(duration))
    minutes = duration_int // 60
    seconds = duration_int % 60
    duration_formatted = f"{minutes}:{seconds:02d}"

    # Parse upload date
    upload_date_formatted = upload_date
    if len(upload_date) == 8:
        try:
            dt = datetime.strptime(upload_date, "%Y%m%d")
            upload_date_formatted = dt.strftime("%B %d, %Y")
        except:
            pass

    # Format view count
    view_count_formatted = (
        f"{int(view_count):,}" if view_count.isdigit() else view_count
    )

    markdown_content = f"""# {title}

## Video Metadata

- **Title**: {title}
- **Channel**: {uploader}
- **Video ID**: COtibNznlP4
- **URL**: {url}
- **Upload Date**: {upload_date_formatted}
- **Duration**: {duration_formatted}
- **Views**: {view_count_formatted}
- **Transcript Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Description

{description}

## Full Transcript

> **Note**: This transcript was extracted from YouTube's automatic captions and may contain errors. Timestamps are preserved for reference.

"""

    # Add transcript segments
    for segment in segments:
        start_time = segment["start"][:8]  # Remove milliseconds for readability
        markdown_content += f"**{start_time}** {segment['text']}\n\n"

    # Write to file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    print(f"✅ Markdown transcript created: {output_file}")
    return output_file


def run_diarization(audio_file, output_dir):
    """Run diarization on the audio file."""
    print("🎙️ Running speaker diarization...")

    cmd = [
        sys.executable,
        "-m",
        "knowledge_system",
        "transcribe",
        "--input",
        str(audio_file),
        "--output",
        str(output_dir),
        "--model",
        "base",
        "--format",
        "vtt",
        "--speaker-labels",
        "--overwrite",
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=900
        )  # 15 min timeout

        if result.returncode == 0:
            print("✅ Diarization completed successfully")

            # Look for diarized VTT file
            diarized_files = list(output_dir.glob("*transcript.vtt"))
            if diarized_files:
                latest_vtt = max(diarized_files, key=lambda x: x.stat().st_mtime)
                print(f"📄 Diarized VTT: {latest_vtt}")

                # Check if it has speaker labels
                with open(latest_vtt) as f:
                    content = f.read()
                    if "<v Speaker_" in content:
                        print("🎯 Speaker labels detected in diarized transcript!")
                        return latest_vtt
                    else:
                        print("⚠️ Diarization completed but no speaker labels found")
                        return None
            else:
                print("❌ No diarized VTT file found")
                return None
        else:
            print(f"❌ Diarization failed: {result.stderr}")
            return None

    except subprocess.TimeoutExpired:
        print("⏰ Diarization timed out (>15 minutes)")
        return None
    except Exception as e:
        print(f"❌ Diarization error: {e}")
        return None


def merge_diarization_with_transcript(
    original_segments, diarized_vtt_file, output_file
):
    """Merge diarization speaker labels with original transcript."""
    print("🔗 Merging diarization with original transcript...")

    # Parse diarized VTT
    diarized_segments = parse_vtt_to_text(diarized_vtt_file)

    # Read the original markdown file
    with open(output_file, encoding="utf-8") as f:
        content = f.read()

    # Find the transcript section and replace it
    transcript_start = content.find("## Full Transcript")
    if transcript_start == -1:
        print("❌ Could not find transcript section in markdown")
        return

    # Keep everything before the transcript section
    header_content = content[:transcript_start]

    # Create new transcript section with diarization
    new_transcript = """## Full Transcript (With Speaker Diarization)

> **Note**: This transcript includes speaker diarization using pyannote.audio. Original timestamps from YouTube captions are preserved.

"""

    for segment in diarized_segments:
        start_time = segment["start"][:8]  # Remove milliseconds
        text = segment["text"]

        # Check if this segment has speaker labels
        if "<v Speaker_" in text:
            # Extract speaker and clean text
            speaker_match = re.search(r"<v (Speaker_\d+)>(.*?)</v>", text)
            if speaker_match:
                speaker = speaker_match.group(1)
                clean_text = speaker_match.group(2).strip()
                new_transcript += f"**{start_time}** **{speaker}**: {clean_text}\n\n"
            else:
                new_transcript += f"**{start_time}** {text}\n\n"
        else:
            new_transcript += f"**{start_time}** {text}\n\n"

    # Write updated content
    final_content = header_content + new_transcript
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(final_content)

    print(f"✅ Updated markdown with diarized transcript: {output_file}")


def main():
    """Main function to create comprehensive diarized transcript."""
    project_root = Path(__file__).parent
    test_outputs = project_root / "data" / "test_files" / "Test Outputs"

    # Video metadata
    title = "Jordan Peterson and Sam Harris' EPIC TOP 5 DEBATE MOMENTS | Must-See Clips"
    uploader = "Nextivation"
    duration = "990"  # seconds
    upload_date = "20230503"
    view_count = "79187"
    url = "https://www.youtube.com/watch?v=COtibNznlP4"
    description = """Get ready for an intellectual feast! In this video, we've compiled the TOP 5 DEBATE MOMENTS between two of the most brilliant minds of our time, Jordan Peterson and Sam Harris. From their heated discussions on religion, morality, and politics, to their insightful analyses of human behavior and psychology, these highlights are sure to be thought-provoking. Whether you're a fan of Peterson, Harris, or both, you won't want to miss these mind-blowing moments. Watch now and let us know in the comments which one is your favorite!

// JORDAN PETERSON POSTERS AND WALL ART //
- Explore here: https://l.linklyhq.com/l/1kZZq

Thumbnail photos acquired via Creative Commons license:
Jordan Peterson by Gage Skidmore (face only).jpg
Sam Harris 2016.jpg (Christopher Michel)

Audio created via Eleven Labs

FAIR USE COPYRIGHT DISCLAIMER
Under Section 107 of the Copyright Act 1976, allowance is made for "fair use" for purposes such as criticism, commenting, news reporting, teaching, scholarship, and research."""

    # File paths
    vtt_file = (
        test_outputs
        / "Jordan Peterson and Sam Harris' EPIC TOP 5 DEBATE MOMENTS ｜ Must-See Clips.en.vtt"
    )
    audio_file = (
        test_outputs
        / "Jordan Peterson and Sam Harris' EPIC TOP 5 DEBATE MOMENTS ｜ Must-See Clips.wav"
    )
    output_file = (
        test_outputs
        / "Jordan_Peterson_Sam_Harris_Debate_Moments_Diarized_Transcript.md"
    )

    print("🎯 Creating Comprehensive Diarized Transcript")
    print(f"📁 VTT File: {vtt_file}")
    print(f"🎵 Audio File: {audio_file}")
    print(f"📄 Output: {output_file}")

    # Step 1: Parse VTT to get segments
    print("\n1️⃣ Parsing VTT transcript...")
    segments = parse_vtt_to_text(vtt_file)
    print(f"✅ Parsed {len(segments)} transcript segments")

    # Step 2: Create initial markdown with original transcript
    print("\n2️⃣ Creating initial markdown transcript...")
    create_markdown_transcript(
        title,
        uploader,
        duration,
        upload_date,
        description,
        view_count,
        url,
        segments,
        output_file,
    )

    # Step 3: Run diarization on audio
    print("\n3️⃣ Running speaker diarization...")
    diarized_vtt = run_diarization(audio_file, test_outputs)

    # Step 4: Merge diarization if successful
    if diarized_vtt:
        print("\n4️⃣ Merging diarization with transcript...")
        merge_diarization_with_transcript(segments, diarized_vtt, output_file)
        print("\n🎉 COMPLETE: Diarized transcript with speaker labels created!")
    else:
        print("\n⚠️ Diarization failed - transcript created without speaker labels")

    print(f"\n📋 Final output: {output_file}")
    return output_file


if __name__ == "__main__":
    main()
