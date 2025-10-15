# Foreign Key Audit - Single Base Migration

## Cross-Base Foreign Keys (PROBLEMS)

### HCE → Main
1. **Episode.video_id → MediaSource.media_id**
   - File: `hce_models.py` line 51
   - Issue: Episode (HCEBase) references MediaSource (MainBase)
   - Status: ❌ CAUSES NoReferencedTableError

## Within-Base Foreign Keys (OK)

### Main Base (models.py)
1. Transcript.video_id → MediaSource.media_id ✓
2. Summary.video_id → MediaSource.media_id ✓
3. Summary.transcript_id → Transcript.transcript_id ✓
4. MOCExtraction.video_id → MediaSource.media_id ✓
5. MOCExtraction.summary_id → Summary.summary_id ✓
6. GeneratedFile.video_id → MediaSource.media_id ✓
7. GeneratedFile.transcript_id → Transcript.transcript_id ✓
8. GeneratedFile.summary_id → Summary.summary_id ✓
9. GeneratedFile.moc_id → MOCExtraction.moc_id ✓
10. BrightDataSession.video_id → MediaSource.media_id ✓

### HCE Base (hce_models.py)
1. Claim.episode_id → Episode.episode_id ✓
2. Person.episode_id → Episode.episode_id ✓
3. Concept.episode_id → Episode.episode_id ✓
4. Jargon.episode_id → Episode.episode_id ✓

### System2 Base (system2_models.py) - Uses MainBase
1. JobRun.job_id → Job.job_id ✓
2. LLMRequest.job_run_id → JobRun.run_id ✓
3. LLMResponse.request_id → LLMRequest.request_id ✓

### Speaker Base (speaker_models.py)
1. SpeakerAssignment.voice_id → SpeakerVoice.id ✓
2. SpeakerLearningHistory.voice_id → SpeakerVoice.id ✓

## Summary

**Total Foreign Keys**: 20
**Cross-Base FKs (Broken)**: 1
**Within-Base FKs (Working)**: 19

**Primary Issue**: Episode.video_id → MediaSource.media_id crosses base boundaries

**Solution**: Merge all models into single Base to make all FKs within-base.
