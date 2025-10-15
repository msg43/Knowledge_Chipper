"""
Bright Data JSON response adapters for Knowledge System.

Provides compatibility layer between Bright Data JSON responses and existing
YouTubeMetadata/YouTubeTranscript Pydantic models to ensure seamless integration.
"""

import re
from datetime import datetime
from typing import Any

from ..logger import get_logger


# Avoid circular imports by importing at runtime
def get_youtube_metadata_class():
    from ..processors.youtube_metadata import YouTubeMetadata

    return YouTubeMetadata


def get_youtube_transcript_class():
    from ..processors.youtube_transcript import YouTubeTranscript

    return YouTubeTranscript


logger = get_logger(__name__)


class BrightDataAdapter:
    """
    Adapter for converting Bright Data JSON responses to Knowledge System models.

    Provides methods to transform Bright Data YouTube API Scraper responses into
    the existing YouTubeMetadata and YouTubeTranscript Pydantic models.
    """

    @staticmethod
    def adapt_metadata_response(bright_data_response: dict[str, Any], video_url: str):
        """
        Convert Bright Data YouTube metadata response to YouTubeMetadata model.

        Args:
            bright_data_response: Raw JSON response from Bright Data YouTube API Scraper
            video_url: Original YouTube URL

        Returns:
            YouTubeMetadata instance compatible with existing processors
        """
        # Use runtime import to avoid circular dependency
        YouTubeMetadata = get_youtube_metadata_class()

        try:
            # Extract video ID from URL or response
            video_id = BrightDataAdapter._extract_video_id(
                video_url, bright_data_response
            )

            # Map Bright Data fields to YouTubeMetadata fields
            metadata_dict = {
                "video_id": video_id,
                "title": BrightDataAdapter._get_title(bright_data_response),
                "url": video_url,
                "description": BrightDataAdapter._get_description(bright_data_response),
                "duration": BrightDataAdapter._get_duration(bright_data_response),
                "view_count": BrightDataAdapter._get_view_count(bright_data_response),
                "like_count": BrightDataAdapter._get_like_count(bright_data_response),
                "comment_count": BrightDataAdapter._get_comment_count(
                    bright_data_response
                ),
                "uploader": BrightDataAdapter._get_uploader(bright_data_response),
                "uploader_id": BrightDataAdapter._get_uploader_id(bright_data_response),
                "upload_date": BrightDataAdapter._get_upload_date(bright_data_response),
                "tags": BrightDataAdapter._get_tags(bright_data_response),
                "categories": BrightDataAdapter._get_categories(bright_data_response),
                "thumbnail_url": BrightDataAdapter._get_thumbnail_url(
                    bright_data_response
                ),
                "caption_availability": BrightDataAdapter._get_caption_availability(
                    bright_data_response
                ),
                "privacy_status": BrightDataAdapter._get_privacy_status(
                    bright_data_response
                ),
                "related_videos": BrightDataAdapter._get_related_videos(
                    bright_data_response
                ),
                "channel_stats": BrightDataAdapter._get_channel_stats(
                    bright_data_response
                ),
                "video_chapters": BrightDataAdapter._get_video_chapters(
                    bright_data_response
                ),
                "extraction_method": "bright_data_api_scraper",
                "fetched_at": datetime.now(),
            }

            # Create and validate YouTubeMetadata instance
            metadata = YouTubeMetadata(**metadata_dict)

            logger.info(
                f"Successfully adapted Bright Data metadata for video {video_id}"
            )
            return metadata

        except Exception as e:
            logger.error(f"Failed to adapt Bright Data metadata response: {e}")
            # Create minimal metadata as fallback
            return BrightDataAdapter._create_fallback_metadata(
                video_url, bright_data_response
            )

    @staticmethod
    def adapt_transcript_response(
        bright_data_response: dict[str, Any], video_url: str, language: str = "en"
    ):
        """
        Convert Bright Data YouTube transcript response to YouTubeTranscript model.

        Args:
            bright_data_response: Raw JSON response from Bright Data YouTube API Scraper
            video_url: Original YouTube URL
            language: Language code for the transcript

        Returns:
            YouTubeTranscript instance compatible with existing processors
        """
        # Use runtime import to avoid circular dependency
        YouTubeTranscript = get_youtube_transcript_class()

        try:
            # Extract video ID from URL or response
            video_id = BrightDataAdapter._extract_video_id(
                video_url, bright_data_response
            )

            # Extract transcript data from Bright Data response
            transcript_data = BrightDataAdapter._get_transcript_data(
                bright_data_response
            )
            # Normalize transcript segments to standard structure with start/end/duration/text
            transcript_data = BrightDataAdapter._normalize_transcript_segments(
                transcript_data
            )

            transcript_text = BrightDataAdapter._get_transcript_text(transcript_data)

            # Map to YouTubeTranscript fields
            transcript_dict = {
                "video_id": video_id,
                "title": BrightDataAdapter._get_title(bright_data_response),
                "url": video_url,
                "language": language,
                "is_manual": BrightDataAdapter._is_manual_transcript(
                    bright_data_response
                ),
                "transcript_text": transcript_text,
                "transcript_data": transcript_data,
                "duration": BrightDataAdapter._get_duration(bright_data_response),
                "uploader": BrightDataAdapter._get_uploader(bright_data_response),
                "upload_date": BrightDataAdapter._get_upload_date(bright_data_response),
                "description": BrightDataAdapter._get_description(bright_data_response),
                "view_count": BrightDataAdapter._get_view_count(bright_data_response),
                "tags": BrightDataAdapter._get_tags(bright_data_response),
                "thumbnail_url": BrightDataAdapter._get_thumbnail_url(
                    bright_data_response
                ),
                "fetched_at": datetime.now(),
            }

            # Create and validate YouTubeTranscript instance
            transcript = YouTubeTranscript(**transcript_dict)

            logger.info(
                f"Successfully adapted Bright Data transcript for video {video_id}"
            )
            return transcript

        except Exception as e:
            logger.error(f"Failed to adapt Bright Data transcript response: {e}")
            # Create minimal transcript as fallback
            return BrightDataAdapter._create_fallback_transcript(
                video_url, bright_data_response
            )

    @staticmethod
    def validate_bright_data_response(response: dict[str, Any]) -> bool:
        """
        Validate that response looks like a Bright Data YouTube API response.

        Args:
            response: JSON response to validate

        Returns:
            True if response appears to be from Bright Data YouTube API
        """
        try:
            # Check for common Bright Data response structure
            if not isinstance(response, dict):
                return False

            # Look for typical YouTube metadata fields
            expected_fields = ["title", "url", "id", "videoId", "videoDetails"]
            has_video_fields = any(field in response for field in expected_fields)

            # Check for Bright Data specific markers
            has_bright_data_markers = (
                "brightdata" in str(response).lower()
                or "scraper" in str(response).lower()
                or "api_response" in response
            )

            return has_video_fields or has_bright_data_markers

        except Exception as e:
            logger.warning(f"Failed to validate Bright Data response: {e}")
            return False

    # Helper methods for field extraction
    @staticmethod
    def _extract_video_id(url: str, response: dict[str, Any]) -> str:
        """Extract video ID from URL or response."""
        # Try to get from response first
        for field in ["id", "videoId", "video_id"]:
            if field in response and response[field]:
                return str(response[field])

        # Extract from URL as fallback
        if "youtu.be/" in url:
            return url.split("youtu.be/")[1].split("?")[0]
        elif "watch?v=" in url:
            return url.split("watch?v=")[1].split("&")[0]
        else:
            raise ValueError(f"Could not extract video ID from URL: {url}")

    @staticmethod
    def _get_title(response: dict[str, Any]) -> str:
        """Extract title from Bright Data response."""
        # Updated for Web Scraper API response format
        for field in ["title", "videoDetails.title", "snippet.title"]:
            value = BrightDataAdapter._get_nested_field(response, field)
            if value:
                return str(value)
        return "Unknown Title"

    @staticmethod
    def _get_description(response: dict[str, Any]) -> str:
        """Extract description from Bright Data response."""
        for field in [
            "description",
            "videoDetails.shortDescription",
            "snippet.description",
        ]:
            value = BrightDataAdapter._get_nested_field(response, field)
            if value:
                return str(value)
        return ""

    @staticmethod
    def _get_duration(response: dict[str, Any]) -> int | None:
        """Extract duration in seconds from Bright Data response."""
        for field in [
            "duration",
            "videoDetails.lengthSeconds",
            "contentDetails.duration",
        ]:
            value = BrightDataAdapter._get_nested_field(response, field)
            if value:
                # Handle different duration formats
                if isinstance(value, (int, float)):
                    return int(value)
                elif isinstance(value, str):
                    # Parse ISO 8601 duration (PT1H2M3S) or seconds string
                    return BrightDataAdapter._parse_duration_string(value)
        return None

    @staticmethod
    def _get_view_count(response: dict[str, Any]) -> int | None:
        """Extract view count from Bright Data response."""
        # Updated for Web Scraper API response format
        for field in [
            "views",  # Web Scraper API field
            "view_count",
            "viewCount",
            "videoDetails.viewCount",
            "statistics.viewCount",
        ]:
            value = BrightDataAdapter._get_nested_field(response, field)
            if value:
                try:
                    return int(str(value).replace(",", ""))
                except (ValueError, TypeError):
                    continue
        return None

    @staticmethod
    def _get_like_count(response: dict[str, Any]) -> int | None:
        """Extract like count from Bright Data response."""
        # Updated for Web Scraper API response format
        for field in ["likes", "like_count", "likeCount", "statistics.likeCount"]:
            value = BrightDataAdapter._get_nested_field(response, field)
            if value:
                try:
                    return int(str(value).replace(",", ""))
                except (ValueError, TypeError):
                    continue
        return None

    @staticmethod
    def _get_comment_count(response: dict[str, Any]) -> int | None:
        """Extract comment count from Bright Data response."""
        # Updated for Web Scraper API response format
        for field in [
            "num_comments",
            "comment_count",
            "commentCount",
            "statistics.commentCount",
        ]:
            value = BrightDataAdapter._get_nested_field(response, field)
            if value:
                try:
                    return int(str(value).replace(",", ""))
                except (ValueError, TypeError):
                    continue
        return None

    @staticmethod
    def _get_uploader(response: dict[str, Any]) -> str:
        """Extract uploader/channel name from Bright Data response."""
        # Updated for Web Scraper API response format
        for field in [
            "youtuber",  # Web Scraper API field
            "uploader",
            "channel",
            "videoDetails.author",
            "snippet.channelTitle",
        ]:
            value = BrightDataAdapter._get_nested_field(response, field)
            if value:
                return str(value)
        return ""

    @staticmethod
    def _get_uploader_id(response: dict[str, Any]) -> str:
        """Extract uploader/channel ID from Bright Data response."""
        for field in [
            "uploader_id",
            "channel_id",
            "videoDetails.channelId",
            "snippet.channelId",
        ]:
            value = BrightDataAdapter._get_nested_field(response, field)
            if value:
                return str(value)
        return ""

    @staticmethod
    def _get_upload_date(response: dict[str, Any]) -> str | None:
        """Extract upload date from Bright Data response."""
        for field in ["upload_date", "uploadDate", "snippet.publishedAt"]:
            value = BrightDataAdapter._get_nested_field(response, field)
            if value:
                # Convert to YYYYMMDD format
                return BrightDataAdapter._parse_date_string(str(value))
        return None

    @staticmethod
    def _get_tags(response: dict[str, Any]) -> list[str]:
        """Extract tags from Bright Data response."""
        for field in ["tags", "videoDetails.keywords", "snippet.tags"]:
            value = BrightDataAdapter._get_nested_field(response, field)
            if value:
                if isinstance(value, list):
                    return [str(tag) for tag in value if tag]
                elif isinstance(value, str):
                    # Split comma-separated tags
                    return [tag.strip() for tag in value.split(",") if tag.strip()]
        return []

    @staticmethod
    def _get_categories(response: dict[str, Any]) -> list[str]:
        """Extract categories from Bright Data response."""
        for field in ["categories", "snippet.categoryId"]:
            value = BrightDataAdapter._get_nested_field(response, field)
            if value:
                if isinstance(value, list):
                    return [str(cat) for cat in value if cat]
                elif isinstance(value, str):
                    return [str(value)]
        return []

    @staticmethod
    def _get_thumbnail_url(response: dict[str, Any]) -> str | None:
        """Extract thumbnail URL from Bright Data response."""
        # Updated for Web Scraper API response format
        for field in [
            "preview_image",  # Web Scraper API field
            "thumbnail",
            "thumbnails.high.url",
            "snippet.thumbnails.high.url",
        ]:
            value = BrightDataAdapter._get_nested_field(response, field)
            if value:
                return str(value)
        return None

    @staticmethod
    def _get_caption_availability(response: dict[str, Any]) -> bool | None:
        """Extract caption availability from Bright Data response."""
        for field in ["caption_availability", "captions", "videoDetails.captions"]:
            value = BrightDataAdapter._get_nested_field(response, field)
            if value is not None:
                if isinstance(value, bool):
                    return value
                elif isinstance(value, str):
                    return value.lower() in ("true", "yes", "available")
        return None

    @staticmethod
    def _get_privacy_status(response: dict[str, Any]) -> str | None:
        """Extract privacy status from Bright Data response."""
        for field in ["privacy_status", "privacyStatus", "status.privacyStatus"]:
            value = BrightDataAdapter._get_nested_field(response, field)
            if value:
                return str(value)
        return None

    @staticmethod
    def _get_transcript_data(response: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract transcript data from Bright Data response."""
        # Updated for Web Scraper API response format
        for field in ["transcript", "formatted_transcript", "captions", "subtitles"]:
            value = BrightDataAdapter._get_nested_field(response, field)
            if value and isinstance(value, list):
                return value
        return []

    @staticmethod
    def _get_transcript_text(transcript_data: list[dict[str, Any]]) -> str:
        """Convert transcript data to plain text."""
        if not transcript_data:
            return ""

        text_parts = []
        for segment in transcript_data:
            if isinstance(segment, dict):
                text = segment.get("text", segment.get("content", ""))
                if text:
                    text_parts.append(str(text).strip())

        return " ".join(text_parts)

    @staticmethod
    def _parse_time_value(value: Any) -> float | None:
        """Parse various time formats (seconds, ms, HH:MM:SS.mmm) into seconds."""
        if value is None:
            return None
        try:
            # Numeric seconds or ms
            if isinstance(value, (int, float)):
                # Heuristic: values > 10000 likely in milliseconds
                return float(value) / 1000.0 if float(value) > 10000 else float(value)
            s = str(value).strip()
            # ISO-like or clock format HH:MM:SS.mmm or MM:SS
            if ":" in s:
                parts = s.split(":")
                parts = [p for p in parts if p != ""]
                if len(parts) == 3:
                    h = float(parts[0])
                    m = float(parts[1])
                    sec = float(parts[2].replace(",", "."))
                    return h * 3600 + m * 60 + sec
                if len(parts) == 2:
                    m = float(parts[0])
                    sec = float(parts[1].replace(",", "."))
                    return m * 60 + sec
            # Plain number string (seconds or ms)
            f = float(s)
            return f / 1000.0 if f > 10000 else f
        except Exception:
            return None

    @staticmethod
    def _normalize_transcript_segments(
        segments: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        """Normalize heterogeneous Bright Data transcript segments to {start,duration,text,speaker?}.

        Supports keys commonly seen in scraper outputs:
        - text keys: text, caption, content, line
        - start keys: start, begin, start_time, startTime, startMs, start_ms, tStartMs, offset
        - end keys: end, end_time, endTime, endMs, end_ms, tEndMs
        - duration keys: duration, dur, durationMs, duration_ms
        - speaker keys: speaker, speaker_name, name
        """
        if not segments:
            return []

        normalized: list[dict[str, Any]] = []

        for raw in segments:
            if not isinstance(raw, dict):
                continue

            # Text
            text = (
                raw.get("text")
                or raw.get("caption")
                or raw.get("content")
                or raw.get("line")
                or ""
            )
            text = str(text).strip()
            if not text:
                continue

            # Start
            start_candidates = [
                raw.get("start"),
                raw.get("begin"),
                raw.get("start_time"),
                raw.get("startTime"),
                raw.get("startMs"),
                raw.get("start_ms"),
                raw.get("tStartMs"),
                raw.get("offset"),
            ]
            start = None
            for v in start_candidates:
                start = BrightDataAdapter._parse_time_value(v)
                if start is not None:
                    break
            if start is None:
                # Fallback: attempt to parse index * 3s later in calling code
                start = 0.0

            # End / duration
            end_candidates = [
                raw.get("end"),
                raw.get("end_time"),
                raw.get("endTime"),
                raw.get("endMs"),
                raw.get("end_ms"),
                raw.get("tEndMs"),
            ]
            end = None
            for v in end_candidates:
                end = BrightDataAdapter._parse_time_value(v)
                if end is not None:
                    break

            duration_candidates = [
                raw.get("duration"),
                raw.get("dur"),
                raw.get("durationMs"),
                raw.get("duration_ms"),
            ]
            duration = None
            for v in duration_candidates:
                duration = BrightDataAdapter._parse_time_value(v)
                if duration is not None:
                    break

            # Derive missing time value
            if end is None and duration is not None:
                end = start + duration
            if duration is None and end is not None:
                duration = max(0.0, end - start)

            # Speaker (optional)
            speaker = raw.get("speaker") or raw.get("speaker_name") or raw.get("name")
            if speaker:
                speaker = str(speaker).strip()

            normalized_seg = {
                "start": float(start or 0.0),
                "duration": float(duration or 0.0),
                "text": text,
            }
            if speaker:
                normalized_seg["speaker"] = speaker

            normalized.append(normalized_seg)

        # Ensure segments are sorted by start time
        try:
            normalized.sort(key=lambda s: s.get("start", 0.0))
        except Exception:
            pass

        return normalized

    @staticmethod
    def _is_manual_transcript(response: dict[str, Any]) -> bool:
        """Determine if transcript is manual or auto-generated."""
        for field in ["is_manual", "manual", "kind"]:
            value = BrightDataAdapter._get_nested_field(response, field)
            if value is not None:
                if isinstance(value, bool):
                    return value
                elif isinstance(value, str):
                    return "manual" in value.lower() or "asr" not in value.lower()
        return False  # Default to auto-generated

    @staticmethod
    def _get_nested_field(data: dict[str, Any], field_path: str) -> Any:
        """Get nested field value using dot notation."""
        try:
            current = data
            for key in field_path.split("."):
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return None
            return current
        except (KeyError, TypeError):
            return None

    @staticmethod
    def _parse_duration_string(duration_str: str) -> int | None:
        """Parse duration string to seconds."""
        try:
            # Try parsing as integer first
            return int(duration_str)
        except ValueError:
            pass

        try:
            # Parse ISO 8601 duration (PT1H2M3S)
            if duration_str.startswith("PT"):
                total_seconds = 0
                # Extract hours, minutes, seconds
                hours_match = re.search(r"(\d+)H", duration_str)
                minutes_match = re.search(r"(\d+)M", duration_str)
                seconds_match = re.search(r"(\d+)S", duration_str)

                if hours_match:
                    total_seconds += int(hours_match.group(1)) * 3600
                if minutes_match:
                    total_seconds += int(minutes_match.group(1)) * 60
                if seconds_match:
                    total_seconds += int(seconds_match.group(1))

                return total_seconds
        except Exception:
            pass

        return None

    @staticmethod
    def _parse_date_string(date_str: str) -> str | None:
        """Parse date string to YYYYMMDD format."""
        try:
            # Try parsing ISO format first
            if "T" in date_str:
                date_obj = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                return date_obj.strftime("%Y%m%d")

            # Try other common formats
            for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"]:
                try:
                    date_obj = datetime.strptime(date_str, fmt)
                    return date_obj.strftime("%Y%m%d")
                except ValueError:
                    continue
        except Exception:
            pass

        return None

    @staticmethod
    def _create_fallback_metadata(url: str, response: dict[str, Any]):
        """Create minimal fallback metadata when adaptation fails."""
        # Use runtime import to avoid circular dependency
        YouTubeMetadata = get_youtube_metadata_class()

        try:
            video_id = BrightDataAdapter._extract_video_id(url, response)
        except ValueError:
            video_id = "unknown"

        return YouTubeMetadata(
            video_id=video_id,
            title=response.get("title", "Unknown Title"),
            url=url,
            extraction_method="bright_data_api_scraper_fallback",
            fetched_at=datetime.now(),
        )

    @staticmethod
    def _create_fallback_transcript(url: str, response: dict[str, Any]):
        """Create minimal fallback transcript when adaptation fails."""
        # Use runtime import to avoid circular dependency
        YouTubeTranscript = get_youtube_transcript_class()

        try:
            video_id = BrightDataAdapter._extract_video_id(url, response)
        except ValueError:
            video_id = "unknown"

        return YouTubeTranscript(
            video_id=video_id,
            title=response.get("title", "Unknown Title"),
            url=url,
            language="en",
            is_manual=False,
            transcript_text="",
            transcript_data=[],
            fetched_at=datetime.now(),
        )

    @staticmethod
    def _get_related_videos(response: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract related videos from Bright Data response."""
        # Updated for Web Scraper API response format
        for field in ["related_videos", "recommendations", "suggested_videos"]:
            value = BrightDataAdapter._get_nested_field(response, field)
            if value and isinstance(value, list):
                # Clean and structure the related videos data
                related = []
                for video in value[:10]:  # Limit to 10 related videos
                    if isinstance(video, dict):
                        related_video = {
                            "video_id": video.get("video_id", ""),
                            "title": video.get("title", ""),
                            "url": video.get("url", ""),
                            "thumbnail": video.get("thumbnail", ""),
                            "duration": video.get("duration", ""),
                            "uploader": video.get("uploader", video.get("channel", "")),
                            "view_count": video.get(
                                "views", video.get("view_count", 0)
                            ),
                        }
                        related.append(related_video)
                return related
        return []

    @staticmethod
    def _get_channel_stats(response: dict[str, Any]) -> dict[str, Any]:
        """Extract detailed channel statistics from Bright Data response."""
        # Updated for Web Scraper API response format
        channel_stats = {}

        # Basic channel info
        for field in ["subscribers", "subscriber_count"]:
            value = BrightDataAdapter._get_nested_field(response, field)
            if value:
                channel_stats["subscribers"] = BrightDataAdapter._parse_count(value)
                break

        # Channel verification status
        for field in ["verified", "is_verified"]:
            value = BrightDataAdapter._get_nested_field(response, field)
            if value is not None:
                channel_stats["verified"] = bool(value)
                break

        # Channel avatar/image
        for field in ["avatar_img_channel", "channel_avatar", "channel_image"]:
            value = BrightDataAdapter._get_nested_field(response, field)
            if value:
                channel_stats["avatar_url"] = str(value)
                break

        # Channel URL
        for field in ["channel_url", "uploader_url"]:
            value = BrightDataAdapter._get_nested_field(response, field)
            if value:
                channel_stats["channel_url"] = str(value)
                break

        # Channel handle/username
        for field in ["handle_name", "channel_handle", "username"]:
            value = BrightDataAdapter._get_nested_field(response, field)
            if value:
                channel_stats["handle"] = str(value)
                break

        return channel_stats

    @staticmethod
    def _get_video_chapters(response: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract video chapters/timestamps from Bright Data response."""
        # Updated for Web Scraper API response format
        for field in ["chapters", "video_chapters", "timestamps", "segments"]:
            value = BrightDataAdapter._get_nested_field(response, field)
            if value and isinstance(value, list):
                chapters = []
                for chapter in value:
                    if isinstance(chapter, dict):
                        chapter_data = {
                            "title": chapter.get("title", chapter.get("name", "")),
                            "start_time": chapter.get(
                                "start_time", chapter.get("start", 0)
                            ),
                            "end_time": chapter.get("end_time", chapter.get("end", 0)),
                            "duration": chapter.get("duration", 0),
                            "thumbnail": chapter.get("thumbnail", ""),
                        }
                        chapters.append(chapter_data)
                return chapters
        return []


# Convenience functions
def adapt_bright_data_metadata(response: dict[str, Any], url: str):
    """Convenience function to adapt Bright Data metadata response."""
    return BrightDataAdapter.adapt_metadata_response(response, url)


def adapt_bright_data_transcript(
    response: dict[str, Any], url: str, language: str = "en"
):
    """Convenience function to adapt Bright Data transcript response."""
    return BrightDataAdapter.adapt_transcript_response(response, url, language)


def validate_bright_data_response(response: dict[str, Any]) -> bool:
    """Convenience function to validate Bright Data response."""
    return BrightDataAdapter.validate_bright_data_response(response)
