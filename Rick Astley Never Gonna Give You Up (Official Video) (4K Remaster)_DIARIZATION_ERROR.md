# Diarization Error Report

**Video:** {transcript.title}
**Video ID:** {transcript.video_id}
**URL:** {url}
**Error Time:** {datetime.now().isoformat()}

## Error Details
Diarization processing failed for this video. The transcript was not saved to allow re-processing with diarization once the issue is resolved.

## Troubleshooting
1. Verify yt-dlp installation and dependencies
2. Ensure sufficient disk space for audio download
4. Check diarization model dependencies (pyannote.audio, etc.)

## Next Steps
- Fix the underlying issue
- Re-run the transcript extraction with diarization enabled
- This error file will be overwritten when processing succeeds
