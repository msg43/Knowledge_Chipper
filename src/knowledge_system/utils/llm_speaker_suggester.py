"""
LLM Speaker Suggestion Module

Simple approach: LLM reads metadata + first 5 statements per speaker and makes best guess.
User can override anything in the popup dialog.
"""

import json

from ..config import get_settings
from ..logger import get_logger
from ..utils.llm_providers import UnifiedLLMClient

logger = get_logger(__name__)


class LLMSpeakerSuggester:
    """Simple LLM-based speaker name suggestions."""

    def __init__(self):
        """Initialize the LLM speaker suggester."""
        self.settings = get_settings()
        self.llm_client = None
        self._initialize_llm()

    def _initialize_llm(self):
        """Initialize LLM client for suggestions."""
        try:
            # Try to use configured LLM (cloud or local)
            if self._try_configured_llm():
                return

            # Try to use MVP LLM if available
            if self._try_mvp_llm():
                return

            # No LLM available
            logger.info(
                "No LLM available - speaker suggestions will use smart fallback"
            )
            self.llm_client = None

        except Exception as e:
            logger.info(f"LLM initialization failed - using smart fallback: {e}")
            self.llm_client = None

    def _try_configured_llm(self) -> bool:
        """Try to initialize with user's configured LLM."""
        try:
            # Check if cloud LLM is configured
            if (
                self.settings.llm.provider == "openai"
                and self.settings.api_keys.openai_api_key
            ):
                self.llm_client = UnifiedLLMClient(
                    provider=self.settings.llm.provider,
                    model=self.settings.llm.model,
                    temperature=0.3,
                )
                logger.info(
                    f"Using configured LLM: {self.settings.llm.provider}/{self.settings.llm.model}"
                )
                return True
            elif (
                self.settings.llm.provider == "anthropic"
                and self.settings.api_keys.anthropic_api_key
            ):
                self.llm_client = UnifiedLLMClient(
                    provider=self.settings.llm.provider,
                    model=self.settings.llm.model,
                    temperature=0.3,
                )
                logger.info(
                    f"Using configured LLM: {self.settings.llm.provider}/{self.settings.llm.model}"
                )
                return True

            # Check if local LLM is configured
            if self.settings.llm.provider == "local":
                self.llm_client = UnifiedLLMClient(
                    provider="local",
                    model=self.settings.llm.local_model,
                    temperature=0.3,
                )
                logger.info(
                    f"Using configured local LLM: {self.settings.llm.local_model}"
                )
                return True

            return False

        except Exception as e:
            logger.debug(f"Configured LLM not available: {e}")
            return False

    def _try_mvp_llm(self) -> bool:
        """Try to initialize with MVP LLM."""
        try:
            from .mvp_llm_setup import get_mvp_llm_setup

            setup = get_mvp_llm_setup()
            if setup.is_mvp_ready():
                mvp_model = setup.get_available_mvp_model()
                if mvp_model:
                    self.llm_client = UnifiedLLMClient(
                        provider="local",
                        model=mvp_model,
                        temperature=0.3,
                    )
                    logger.info(f"Using MVP LLM: {mvp_model}")
                    return True

            return False

        except Exception as e:
            logger.debug(f"MVP LLM not available: {e}")
            return False

    def suggest_speaker_names(
        self,
        speaker_segments: dict[str, list[dict]],
        metadata: dict | None = None,
        known_hosts: list[str] | None = None,
    ) -> dict[str, tuple[str, float]]:
        """
        Suggest speaker names using LLM with optional known host context.

        Known hosts (from channel mappings) are provided as context to help the LLM
        match speakers to names based on content analysis.

        Args:
            speaker_segments: Dict mapping speaker_id to list of speech segments
            metadata: Video/podcast metadata (title, description, channel, etc.)
            known_hosts: Optional list of known host names for this channel
                        (e.g., ["Jeff Snider", "Emil Kalinowski"])
                        LLM will determine which speaker is which

        Returns:
            Dict mapping speaker_id to (suggested_name, confidence_score)
        """
        # If we have known hosts, log them
        if known_hosts:
            logger.info(f"📺 Channel has {len(known_hosts)} known hosts: {known_hosts}")
            logger.info(
                f"   → LLM will match speakers to these names based on transcript content"
            )

        # If no LLM available, use fallback (can't effectively use host context without LLM)
        if not self.llm_client:
            logger.info("No LLM configured - using pattern-based fallback")
            return self._simple_fallback(speaker_segments)

        try:
            # Debug logging
            logger.debug(f"LLM suggester called with {len(speaker_segments)} speakers")
            logger.debug(
                f"Metadata keys: {list(metadata.keys()) if metadata else 'None'}"
            )
            for speaker_id, segments in speaker_segments.items():
                logger.debug(f"  {speaker_id}: {len(segments)} segments")

            # Create simple prompt with metadata + first 5 statements per speaker
            # Include known hosts as context
            prompt = self._create_simple_prompt(speaker_segments, metadata, known_hosts)

            # Debug log the prompt
            logger.debug(f"Generated prompt (first 500 chars): {prompt[:500]}...")

            # Get LLM suggestions
            response = self.llm_client.generate(prompt=prompt)

            # Debug log the response
            logger.debug(f"LLM response (first 500 chars): {response.content[:500]}...")

            # Parse response
            suggestions = self._parse_suggestions(response.content, speaker_segments)

            # Validate and fix suggestions to enforce critical rules
            suggestions = self._validate_and_fix_suggestions(
                suggestions, speaker_segments
            )

            # Boost confidence for speakers matched to known hosts
            if known_hosts:
                for speaker_id, (name, conf) in suggestions.items():
                    if name in known_hosts:
                        # LLM matched this speaker to a known host - high confidence!
                        suggestions[speaker_id] = (name, 0.95)
                        logger.info(
                            f"🎯 LLM matched speaker to known host: {speaker_id} → '{name}' "
                            f"(confidence boosted to 0.95)"
                        )

            logger.info(f"LLM suggested names for {len(suggestions)} speakers")
            for speaker_id, (name, conf) in suggestions.items():
                logger.info(f"  {speaker_id} -> '{name}' (confidence: {conf:.2f})")

            # Additional validation: Check for any remaining duplicates
            all_names = [name for name, _ in suggestions.values()]
            unique_names = set(all_names)
            if len(all_names) != len(unique_names):
                # This is actually GOOD if it's a single-speaker video!
                # LLM correctly assigned same name to multiple speaker IDs
                name_counts = {}
                for speaker_id, (name, conf) in suggestions.items():
                    if name not in name_counts:
                        name_counts[name] = []
                    name_counts[name].append(speaker_id)

                for name, speaker_ids in name_counts.items():
                    if len(speaker_ids) > 1:
                        logger.info(
                            f"✅ LLM correctly assigned '{name}' to {len(speaker_ids)} speaker IDs: {speaker_ids}"
                        )
                        logger.info(
                            f"   This is CORRECT behavior for single-speaker content that was over-segmented by diarization"
                        )

            # Check if we have multiple speakers but only one unique name
            # This suggests single-speaker content that was over-segmented
            if len(speaker_segments) > 1 and len(unique_names) == 1:
                logger.info(
                    f"🎯 SINGLE-SPEAKER DETECTION: {len(speaker_segments)} speaker IDs but only 1 unique name ('{list(unique_names)[0]}')"
                )
                logger.info(
                    f"   This indicates diarization over-segmented a monologue/solo podcast"
                )

            return suggestions

        except Exception as e:
            logger.error(f"LLM suggestion failed: {e}", exc_info=True)
            return self._simple_fallback(speaker_segments)

    def _create_simple_prompt(
        self,
        speaker_segments: dict[str, list[dict]],
        metadata: dict | None,
        known_hosts: list[str] | None = None,
    ) -> str:
        """
        Create smart podcast-focused prompt with full metadata + first 3 minutes of content.

        Args:
            speaker_segments: Speaker segments to analyze
            metadata: Video/podcast metadata. Can be either:
                     - Old format: Single dict with fields (backward compatible)
                     - New format: {'primary_source': {...}, 'aliased_sources': [...]}
            known_hosts: Optional list of known host names for this channel
                        (e.g., ["Jeff Snider", "Emil Kalinowski"])
        """

        # Build comprehensive metadata section (don't truncate description)
        metadata_text = "No metadata available"
        if metadata:
            # Check if this is multi-source format
            if "primary_source" in metadata or "aliased_sources" in metadata:
                # New multi-source format
                parts = []

                primary = metadata.get("primary_source", {})
                aliases = metadata.get("aliased_sources", [])

                # Primary source metadata
                if primary and primary.get("title"):
                    parts.append(
                        f"PRIMARY SOURCE ({primary.get('source_type', 'unknown').upper()}):"
                    )
                    parts.append(f"  Title: {primary.get('title')}")

                    if primary.get("description"):
                        parts.append(f"  Description: {primary.get('description')}")

                    if primary.get("uploader") or primary.get("author"):
                        channel = primary.get("uploader") or primary.get("author")
                        parts.append(f"  Channel/Author: {channel}")

                        # Check for learned channel mapping
                        try:
                            from ..database.speaker_models import get_speaker_db_service

                            db_service = get_speaker_db_service()
                            known_host = db_service.get_channel_host_mapping(channel)
                            if known_host:
                                parts.append(
                                    f"  Known Host: {known_host} (from previous corrections)"
                                )
                        except Exception as e:
                            logger.debug(f"Could not check channel mapping: {e}")

                    if primary.get("channel_id"):
                        parts.append(f"  Channel ID: {primary.get('channel_id')}")
                    if primary.get("url"):
                        parts.append(f"  URL: {primary.get('url')}")

                # Aliased sources metadata
                for i, alias in enumerate(aliases, 1):
                    if alias and alias.get("title"):
                        parts.append(
                            f"\nALIASED SOURCE #{i} ({alias.get('source_type', 'unknown').upper()}):"
                        )
                        parts.append(f"  Title: {alias.get('title')}")

                        if alias.get("description"):
                            # Use FULL description from aliased source (often richer)
                            parts.append(f"  Description: {alias.get('description')}")

                        if alias.get("uploader") or alias.get("author"):
                            channel = alias.get("uploader") or alias.get("author")
                            parts.append(f"  Channel/Author: {channel}")

                        if alias.get("channel_id"):
                            parts.append(f"  Channel ID: {alias.get('channel_id')}")
                        if alias.get("view_count"):
                            parts.append(f"  Views: {alias.get('view_count'):,}")
                        if alias.get("url"):
                            parts.append(f"  URL: {alias.get('url')}")

                if aliases:
                    parts.append(
                        "\nNote: This content is available from multiple platforms. Use ALL available metadata to identify speakers. Longer descriptions typically have more detail about guests."
                    )

                if parts:
                    metadata_text = "\n".join(parts)

            else:
                # Old single-source format (backward compatibility)
                parts = []
                if metadata.get("title"):
                    parts.append(f"Title: {metadata['title']}")
                if metadata.get("uploader"):
                    channel_name = metadata["uploader"]
                    parts.append(f"Channel: {channel_name}")

                    # Check if we have a learned mapping for this channel
                    try:
                        from ..database.speaker_models import get_speaker_db_service

                        db_service = get_speaker_db_service()
                        known_host = db_service.get_channel_host_mapping(channel_name)
                        if known_host:
                            parts.append(
                                f"Known Host: {known_host} (from previous corrections)"
                            )
                    except Exception as e:
                        logger.debug(f"Could not check channel mapping: {e}")

                if metadata.get("description"):
                    # Use FULL description for name extraction
                    parts.append(f"Description: {metadata['description']}")
                # Add any other useful metadata
                if metadata.get("channel_id"):
                    parts.append(f"Channel ID: {metadata['channel_id']}")
                if metadata.get("uploader_id"):
                    parts.append(f"Uploader ID: {metadata['uploader_id']}")
                if parts:
                    metadata_text = "\n".join(parts)

        # Build speaker sections with first 3 minutes of content (180 seconds)
        # Extended from 2 to 3 minutes to capture speakers who don't speak immediately
        speaker_sections: list[str] = []
        # Use a stable order for keys to reduce variability between runs
        ordered_speaker_ids = sorted(speaker_segments.keys())

        for speaker_id in ordered_speaker_ids:
            segments = speaker_segments.get(speaker_id, [])
            # Sort by start time if available
            segments_sorted = sorted(
                segments,
                key=lambda s: (
                    s.get("start", float("inf")),
                    s.get("end", float("inf")),
                ),
            )

            # 🎯 OPTIMIZATION: Use all 5 clean segments (post-deduplication)
            # This analyzes exactly what the user sees in the speaker attribution dialog
            all_clean_segments = []
            for seg in segments_sorted[
                :5
            ]:  # Take first 5 segments (guaranteed unique & clean)
                text = str(seg.get("text", "")).strip()
                if text and len(text) > 3:  # Include short statements like "I'm Tony"
                    all_clean_segments.append(text)

            # Debug logging
            logger.debug(
                f"Speaker {speaker_id} has {len(all_clean_segments)} clean segments from {len(segments)} total segments"
            )

            speaker_section = f"\n{speaker_id} (5 clean segments):"
            if all_clean_segments:
                # Join all segments with natural flow
                combined_text = " ".join(all_clean_segments)
                # More generous length limit since we're analyzing exactly what user sees
                if len(combined_text) > 1200:
                    combined_text = combined_text[:1200] + "..."
                speaker_section += f'\n  "{combined_text}"'
            else:
                speaker_section += "\n  (No clean speech segments available)"

            speaker_sections.append(speaker_section)

        speakers_text = "".join(speaker_sections)

        # Build a strict JSON skeleton with the exact keys we expect
        skeleton_lines = [
            f'    "{sid}": {{"name": "", "confidence": 0.5}}'
            for sid in ordered_speaker_ids
        ]
        json_skeleton = "{\n" + ",\n".join(skeleton_lines) + "\n}"

        # Count speakers for explicit validation
        num_speakers = len(ordered_speaker_ids)

        # Build known hosts section if available
        known_hosts_section = ""
        if known_hosts:
            known_hosts_section = (
                "\n📺 CHANNEL CONTEXT - Known Host(s) for this channel:\n"
            )
            for host_name in known_hosts:
                known_hosts_section += f"  • {host_name}\n"
            known_hosts_section += (
                "\nIMPORTANT: One or more speakers in the transcript should match these names.\n"
                "Use self-introductions, direct address patterns, and context to determine WHICH speaker is WHICH host.\n"
                "If a speaker says 'I'm Jeff' or is addressed as 'Jeff', and Jeff Snider is a known host, assign 'Jeff Snider'.\n\n"
            )
            logger.info(
                f"📝 LLM prompt includes {len(known_hosts)} known hosts as context: {known_hosts}"
            )

        prompt = (
            "You are identifying speakers in a podcast/interview transcript.\n\n"
            f"SPEAKER DETECTION: The diarization system detected {num_speakers} speaker ID(s). HOWEVER, diarization can sometimes incorrectly split ONE person into multiple IDs.\n\n"
            f"{known_hosts_section}"
            "🚨 CRITICAL RULES - VIOLATION = FAILURE 🚨\n"
            "1. SKEPTICALLY EVALUATE: Before assigning different names, determine if multiple speaker IDs are actually the SAME person\n"
            "   - Check if speech patterns, vocabulary, and topics are similar across speaker IDs\n"
            "   - Check if metadata indicates a single-speaker format (solo podcast, monologue, commentary)\n"
            "   - If speaker IDs appear to be the same person, assign the SAME name to all of them\n"
            "2. NO EMPTY NAMES: Every speaker MUST have a name assigned\n"
            "3. NO GENERIC LABELS: NEVER use 'Speaker 1', 'Speaker 2', 'Unknown Speaker' or similar generic labels\n"
            "4. METADATA NAMES WIN: Title/description names ALWAYS beat speech transcription variants\n"
            "5. PHONETIC MATCHING: 'Stacy Rasgon' (title) beats 'Stacey Raskin' (speech transcription error)\n"
            "6. WHEN UNCERTAIN: Infer descriptive names from context, roles, or characteristics\n\n"
            "VALIDATION CHECK: Verify that speakers with DIFFERENT names are actually DIFFERENT people, not diarization errors.\n\n"
            "CONTEXT: In most podcasts:\n"
            "- Guest names are mentioned in the description/title\n"
            "- Host names may be in the description or can be inferred from channel name\n"
            "- Both speakers typically introduce themselves or each other in the first 2 minutes\n\n"
            "NAMING PRIORITY (highest to lowest):\n"
            "1. PROPER NAMES from metadata (title, description, channel)\n"
            "2. PROPER NAMES from self-introductions in transcript ('I'm Tony', 'my name is...', etc.)\n"
            "3. INFERRED NAMES from context (e.g., 'The Investor' if discussing portfolio, 'The Professor' if academic)\n"
            "4. ROLE-BASED NAMES if absolutely no other clues (e.g., 'Host', 'Guest Expert', 'Interviewer')\n\n"
            "EXAMPLES OF GOOD NAMES:\n"
            "✅ 'Jeff Snider' (from metadata)\n"
            "✅ 'Tony' (from self-introduction)\n"
            "✅ 'The Economics Professor' (inferred from content)\n"
            "✅ 'Financial Analyst' (inferred from expertise)\n\n"
            "EXAMPLES OF FORBIDDEN NAMES:\n"
            "❌ 'Speaker 1'\n"
            "❌ 'Speaker 2'\n"
            "❌ 'Unknown Speaker'\n"
            "❌ 'Person A'\n\n"
            "INSTRUCTIONS:\n"
            "- Extract proper names from the FULL metadata (especially title/description) and clean speech segments\n"
            "- Look for introductions like 'I'm Tony', 'my name is...', 'welcome back, I'm...', 'today's guest is...'\n"
            "- When you find phonetically similar names in metadata vs speech, ALWAYS prefer the metadata version\n"
            "- Channel names like 'Eurodollar University' often map to host names found in the description\n"
            "- If you cannot find a proper name, infer a descriptive name from the speaker's role or expertise\n"
            "- Output STRICTLY VALID JSON ONLY. No markdown, no prose, no comments.\n"
            "- Confidence: 0.8-1.0 for proper names, 0.5-0.7 for inferred names, 0.3-0.4 for role-based names\n\n"
            f"METADATA:\n{metadata_text}\n\n"
            f"SPEAKERS (clean deduplicated segments - exactly what user sees):\n{speakers_text}\n\n"
            f"⚠️  FINAL CHECK: Ensure all {num_speakers} speakers have DIFFERENT, DESCRIPTIVE (not generic) names before responding.\n\n"
            "Return only a single JSON object matching this skeleton (fill in values):\n"
            f"{json_skeleton}\n"
        )

        return prompt

    def _validate_and_fix_suggestions(
        self,
        suggestions: dict[str, tuple[str, float]],
        speaker_segments: dict[str, list[dict]],
    ) -> dict[str, tuple[str, float]]:
        """Validate and fix suggestions to enforce critical rules."""
        try:
            # Rule 1: Ensure every speaker has a name (no empty names)
            for speaker_id in speaker_segments.keys():
                if (
                    speaker_id not in suggestions
                    or not suggestions[speaker_id][0].strip()
                ):
                    # 🚨 CRITICAL FIX: LLM failed to provide name for this speaker
                    logger.error(
                        f"🚨 CRITICAL: LLM did not provide name for {speaker_id} - this should NEVER happen!"
                    )
                    logger.error(
                        f"   All suggestions received: {list(suggestions.keys())}"
                    )
                    logger.error(
                        f"   All speakers in segments: {list(speaker_segments.keys())}"
                    )

                    # Assign a descriptive name based on speaker position
                    speaker_num = speaker_id.replace("SPEAKER_", "").lstrip("0") or "0"
                    try:
                        num = int(speaker_num)
                        letter = chr(65 + num)  # A, B, C, ...
                        descriptive_name = f"Unknown Speaker {letter}"
                    except (ValueError, IndexError):
                        descriptive_name = "Unknown Speaker X"
                    suggestions[speaker_id] = (descriptive_name, 0.2)
                    logger.warning(
                        f"Emergency fallback: {speaker_id} -> '{descriptive_name}'"
                    )

            # Rule 2: Check for duplicate names (but this is now ALLOWED if LLM determined they're the same person)
            name_counts = {}
            for speaker_id, (name, conf) in suggestions.items():
                name_lower = name.lower().strip()
                if name_lower in name_counts:
                    name_counts[name_lower].append((speaker_id, name, conf))
                else:
                    name_counts[name_lower] = [(speaker_id, name, conf)]

            # Log duplicate names but DON'T fix them - LLM may have correctly determined they're the same person
            for name_lower, speakers_with_name in name_counts.items():
                if len(speakers_with_name) > 1:
                    logger.info(
                        f"✅ LLM assigned same name '{speakers_with_name[0][1]}' to {len(speakers_with_name)} speaker IDs "
                        f"(likely diarization split same person into multiple IDs)"
                    )
                    # No longer "fixing" duplicates - they're intentional when diarization splits one person

            return suggestions

        except Exception as e:
            logger.error(f"Error validating suggestions: {e}")
            return suggestions

    def _parse_suggestions(
        self, response: str, speaker_segments: dict[str, list[dict]]
    ) -> dict[str, tuple[str, float]]:
        """Parse LLM response into suggestions."""
        try:
            # Extract JSON from response (strip any leading prose or markdown fences)
            response_text = (response or "").strip()
            if response_text.startswith("```"):
                # Remove markdown fence if present
                # e.g., ```json\n{...}\n```
                parts = response_text.split("```")
                # Choose the largest brace-containing part
                candidates = [p for p in parts if "{" in p and "}" in p]
                response_text = (
                    max(candidates, key=len) if candidates else response_text
                )

            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_text = response_text[start_idx:end_idx]
                llm_result = json.loads(json_text)
            else:
                logger.warning("No JSON found in LLM response")
                return self._simple_fallback(speaker_segments)

            # Normalize keys from the model (e.g., SPEAKER_0 -> SPEAKER_00)
            def normalize_key(k: str) -> str:
                k = str(k).strip().upper().replace(" ", "_")
                # Extract numeric suffix if present
                import re

                m = re.search(r"SPEAKER[_\-\s]*(\d+)$", k)
                if m:
                    num = int(m.group(1))
                    return f"SPEAKER_{num:02d}"
                return k

            normalized_llm = {normalize_key(k): v for k, v in dict(llm_result).items()}

            suggestions: dict[str, tuple[str, float]] = {}
            for speaker_id in speaker_segments.keys():
                candidate = None
                if speaker_id in llm_result:
                    candidate = llm_result[speaker_id]
                else:
                    norm_id = normalize_key(speaker_id)
                    if norm_id in normalized_llm:
                        candidate = normalized_llm[norm_id]

                if isinstance(candidate, dict):
                    # Extract speaker number for fallback
                    speaker_num_str = (
                        speaker_id.replace("SPEAKER_", "").lstrip("0") or "0"
                    )
                    try:
                        num = int(speaker_num_str)
                        letter = chr(65 + num)  # A, B, C, ...
                        fallback_name = f"Unknown Speaker {letter}"
                    except (ValueError, IndexError):
                        fallback_name = "Unknown Speaker X"

                    suggested_name = str(candidate.get("name", fallback_name)).strip()
                    # Sanitize name
                    if len(suggested_name) > 60:
                        suggested_name = suggested_name[:57] + "..."
                    if "\n" in suggested_name:
                        suggested_name = " ".join(suggested_name.split())

                    conf_raw = candidate.get("confidence", 0.5)
                    try:
                        confidence = float(conf_raw)
                    except Exception:
                        confidence = 0.5
                    confidence = max(0.1, min(1.0, confidence))

                    suggestions[speaker_id] = (suggested_name, confidence)
                    logger.debug(
                        f"LLM: {speaker_id} -> '{suggested_name}' ({confidence:.1f})"
                    )
                else:
                    # Fallback for missing speakers - use letter-based naming
                    speaker_num_str = (
                        speaker_id.replace("SPEAKER_", "").lstrip("0") or "0"
                    )
                    try:
                        num = int(speaker_num_str)
                        letter = chr(65 + num)
                        fallback_name = f"Unknown Speaker {letter}"
                    except (ValueError, IndexError):
                        fallback_name = "Unknown Speaker X"
                    suggestions[speaker_id] = (fallback_name, 0.3)

            return suggestions

        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return self._simple_fallback(speaker_segments)

    def _simple_fallback(
        self, speaker_segments: dict[str, list[dict]]
    ) -> dict[str, tuple[str, float]]:
        """
        Smart fallback when LLM is not available.

        Attempts to extract names from self-introductions in the transcript.
        If that fails, uses descriptive names instead of generic "Speaker X".
        """
        suggestions = {}

        # Try to extract names from self-introductions
        import re

        name_pattern = re.compile(
            r"\b(?:I\'?m|my name is|this is|I am|call me)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            re.IGNORECASE,
        )

        for i, (speaker_id, segments) in enumerate(sorted(speaker_segments.items())):
            found_name = None

            # Check first few segments for self-introduction
            for segment in segments[:5]:
                text = segment.get("text", "")
                match = name_pattern.search(text)
                if match:
                    found_name = match.group(1).title()
                    break

            if found_name:
                suggestions[speaker_id] = (found_name, 0.6)
            else:
                # Use letter-based unknown names (Unknown Speaker A, B, C, etc.)
                suggestions[speaker_id] = (f"Unknown Speaker {chr(65+i)}", 0.3)

        logger.info("No LLM available - using pattern-based name extraction")
        return suggestions

    def _force_fix_duplicates(
        self, suggestions: dict[str, tuple[str, float]]
    ) -> dict[str, tuple[str, float]]:
        """Emergency fix for any remaining duplicate names."""
        logger.warning("🚨 EMERGENCY: Force-fixing duplicate speaker names")

        # Create mapping of names to speaker IDs
        name_to_speakers = {}
        for speaker_id, (name, conf) in suggestions.items():
            name_lower = name.lower().strip()
            if name_lower not in name_to_speakers:
                name_to_speakers[name_lower] = []
            name_to_speakers[name_lower].append((speaker_id, name, conf))

        # Fix duplicates by using generic names
        fixed_suggestions = {}
        for name_lower, speaker_list in name_to_speakers.items():
            if len(speaker_list) == 1:
                # No duplicate, keep as is
                speaker_id, name, conf = speaker_list[0]
                fixed_suggestions[speaker_id] = (name, conf)
            else:
                # Multiple speakers with same name - assign letter-based names
                logger.error(
                    f"Force-fixing {len(speaker_list)} speakers with duplicate name '{speaker_list[0][1]}'"
                )
                for i, (speaker_id, _, conf) in enumerate(speaker_list):
                    # Use letter-based naming for duplicates
                    letter = chr(65 + len(fixed_suggestions))  # A, B, C, ...
                    descriptive_name = f"Unknown Speaker {letter}"
                    fixed_suggestions[speaker_id] = (
                        descriptive_name,
                        0.3,
                    )  # Low confidence for forced fix
                    logger.warning(f"Force-fixed {speaker_id} -> '{descriptive_name}'")

        return fixed_suggestions


def suggest_speaker_names_with_llm(
    speaker_segments: dict[str, list[dict]],
    metadata: dict | None = None,
    known_hosts: list[str] | None = None,
) -> dict[str, tuple[str, float]]:
    """
    Convenience function for LLM speaker suggestions.

    Args:
        speaker_segments: Dict mapping speaker_id to list of speech segments
        metadata: Optional metadata (title, description, etc.)
        known_hosts: Optional list of known host names for this channel
                    (e.g., ["Jeff Snider", "Emil Kalinowski"])
                    LLM will match speakers to these names based on content

    Returns:
        Dict mapping speaker_id to (suggested_name, confidence_score)
    """
    suggester = LLMSpeakerSuggester()
    return suggester.suggest_speaker_names(speaker_segments, metadata, known_hosts)
