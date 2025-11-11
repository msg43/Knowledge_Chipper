# Queue Tab Manual Verification Plan

## Prerequisites

1. **Apply Database Migration**
   ```bash
   sqlite3 data/knowledge_system.db < src/knowledge_system/database/migrations/2025_11_05_source_stage_status.sql
   ```

2. **Verify Migration Success**
   ```bash
   sqlite3 data/knowledge_system.db ".tables" | grep source_stage_statuses
   ```

## Test Scenarios

### 1. Basic Queue Display
**Steps:**
1. Launch the GUI application
2. Click on the "Queue" tab (should appear between "Summarize" and "Review")
3. Verify empty table displays with correct columns:
   - Title, URL, Current Stage, Status, Progress, Duration, Worker, Actions

**Expected Result:**
- Table shows "No items in queue" or empty rows
- Stats header shows "Total: 0 | In Progress: 0 | Completed: 0 | Failed: 0"

### 2. Download Queue Tracking
**Steps:**
1. Go to Transcription tab
2. Add 3-5 YouTube URLs to download
3. Start download process
4. Immediately switch to Queue tab

**Expected Result:**
- URLs appear in queue with stage="Download", status="queued"
- As downloads start, status changes to "in_progress"
- Worker column shows "Account_1" or similar
- Progress updates in real-time
- Completed downloads show status="completed" with green background

### 3. Transcription Pipeline
**Steps:**
1. Select a downloaded video from Process tab
2. Start transcription
3. Switch to Queue tab
4. Monitor progress

**Expected Result:**
- Stage changes from "Download" to "Transcription"
- Status shows "in_progress" with yellow/green background
- Progress percentage updates during processing
- On completion, status="completed"
- Duration column shows elapsed time

### 4. Local File Processing
**Steps:**
1. Go to Transcription tab
2. Select "Local Audio Files" 
3. Choose a local .mp3 or .wav file
4. Start transcription
5. Check Queue tab

**Expected Result:**
- Download stage shows status="skipped" (gray background)
- Transcription stage shows normal progress
- Metadata indicates "local_file" reason for skip

### 5. Multi-Stage Pipeline
**Steps:**
1. Process a file through full pipeline:
   - Download from YouTube
   - Transcribe with Whisper
   - Summarize with HCE mode
2. Monitor each stage in Queue tab

**Expected Result:**
- Single row shows current stage progress
- Historical stages can be inferred from status
- Each stage transition is visible in real-time

### 6. Filter Testing
**Steps:**
1. Process multiple files to create variety
2. Test Stage filter dropdown:
   - Select "Download" - only download items show
   - Select "Transcription" - only transcription items show
3. Test Status filter:
   - Select "In Progress" - only active items show
   - Select "Failed" - only failed items show

**Expected Result:**
- Filters work correctly
- Pagination updates based on filtered results
- "All Stages"/"All Statuses" shows everything

### 7. Error Handling
**Steps:**
1. Cause deliberate failure:
   - Invalid YouTube URL
   - Cancel during transcription
   - Use invalid API key for summarization
2. Check Queue tab display

**Expected Result:**
- Failed items show status="failed" with red background
- Error details in metadata (viewable in future detail modal)
- Stats header updates failed count

### 8. Auto-Refresh
**Steps:**
1. Start a long-running process (large file transcription)
2. Watch Queue tab without interaction
3. Time the refresh interval

**Expected Result:**
- Table updates every 5 seconds automatically
- No flickering or loss of selection
- Progress smoothly increments

### 9. Pagination
**Steps:**
1. Process 60+ items to exceed page size
2. Test pagination controls

**Expected Result:**
- Shows "Page 1 of 2" correctly
- Next/Previous buttons work
- Current page items display properly

### 10. Performance Test
**Steps:**
1. Process 100+ items
2. Monitor GUI responsiveness
3. Check database query performance

**Expected Result:**
- GUI remains responsive
- No lag when switching to Queue tab
- Filtering/pagination is instant

## Verification Checklist

- [ ] Queue tab appears in correct position
- [ ] Empty state displays correctly
- [ ] Downloads track properly
- [ ] Transcriptions show progress
- [ ] Summarizations update status
- [ ] Local files show "skipped" for download
- [ ] Filters work correctly
- [ ] Auto-refresh functions (5 second interval)
- [ ] Stats update accurately
- [ ] Failed items display properly
- [ ] Pagination works for large datasets
- [ ] No memory leaks during extended use
- [ ] Database queries are performant

## Known Limitations

1. **Detail Modal**: Not yet implemented - double-click shows log message only
2. **Progress Granularity**: Some stages only show 0% or 100%
3. **ETA Calculation**: Not yet implemented
4. **Column Sorting**: Not yet implemented
5. **Export Function**: Not yet implemented

## Debug Commands

If issues arise, check:

```sql
-- View all stage statuses
SELECT * FROM source_stage_statuses ORDER BY last_updated DESC LIMIT 20;

-- Check specific source
SELECT * FROM source_stage_statuses WHERE source_id = 'YOUR_SOURCE_ID';

-- Count by stage and status
SELECT stage, status, COUNT(*) 
FROM source_stage_statuses 
GROUP BY stage, status;
```

## Success Criteria

The Queue Tab is considered successfully implemented when:

1. All test scenarios pass without errors
2. Real-time updates work reliably
3. Performance remains good with 100+ items
4. No crashes or freezes occur
5. User can effectively monitor pipeline progress

## Regression Testing

After Queue Tab implementation, verify:

1. Existing tabs still function normally
2. Download process unchanged
3. Transcription works as before
4. Summarization completes successfully
5. No impact on processing speed
6. Database integrity maintained
