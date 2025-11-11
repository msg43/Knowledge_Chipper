# Queue Tab User Guide

## Overview

The Queue tab provides real-time visibility into your Knowledge Chipper processing pipeline. You can monitor the status of all files as they progress through download, transcription, summarization, and analysis stages.

## Accessing the Queue Tab

1. Launch Knowledge Chipper
2. Click on the **Queue** tab in the main window (located between "Summarize" and "Review")

## Understanding the Queue Display

### Table Columns

The queue displays your processing items in a table with the following columns:

- **Title**: The name of the video, document, or file being processed
- **URL**: Source location (YouTube link, file path, etc.)
- **Current Stage**: Which processing step is active (Download, Transcription, etc.)
- **Status**: Current status within that stage
- **Progress**: Percentage complete for the current operation
- **Duration**: How long the current stage has been running
- **Worker**: Which download account or processor is handling this item
- **Actions**: Quick actions (currently shows "View Details")

### Status Colors

Different statuses are color-coded for quick identification:

- 🟡 **Yellow** - Queued: Waiting to start
- 🔵 **Blue** - Scheduled: Has an assigned time slot
- 🟢 **Light Green** - In Progress: Currently processing
- ✅ **Dark Green** - Completed: Successfully finished
- 🔴 **Red** - Failed: An error occurred
- 🟠 **Orange** - Blocked: Temporarily paused (rate limiting)
- ⚪ **Gray** - Not Applicable/Skipped

### Processing Stages

Files progress through these stages in order:

1. **Download** - Fetching audio from YouTube/RSS
2. **Transcription** - Converting audio to text
3. **Summarization** - Analyzing text for key information
4. **HCE Mining** - Extracting claims and entities
5. **Flagship Eval** - Ranking claim importance

## Features

### Real-Time Updates

The queue automatically refreshes every 5 seconds, showing:
- Progress percentage updates
- Status changes
- New items added to the queue
- Completed items

### Statistics Header

At the top of the tab, you'll see overall statistics:
- **Total**: Number of items in the system
- **In Progress**: Items currently being processed
- **Completed**: Successfully finished items
- **Failed**: Items that encountered errors
- **Rate**: Average processing speed (items/hour)

### Filtering

Use the dropdown menus to filter the display:

**Stage Filter:**
- All Stages (default)
- Download only
- Transcription only
- Summarization only
- HCE Mining only
- Flagship Eval only

**Status Filter:**
- All Statuses (default)
- Pending
- Queued
- In Progress
- Completed
- Failed
- Blocked

### Search

Type in the search box to filter by:
- Video/file title
- URL content
- Source ID

### Pagination

For large queues:
- 50 items displayed per page
- Use Previous/Next buttons to navigate
- Current page shown as "Page X of Y"

## Common Scenarios

### Monitoring Downloads

1. Add URLs in the Transcription tab
2. Switch to Queue tab
3. Watch as items progress from "queued" → "in_progress" → "completed"
4. See which account is downloading each file

### Tracking Long Transcriptions

1. Start transcription of large files
2. Queue tab shows progress percentage
3. Duration column shows elapsed time
4. Useful for estimating completion time

### Identifying Failures

1. Failed items appear with red background
2. Status column shows "failed"
3. Check logs for detailed error information
4. Consider retrying failed items

### Managing Rate Limits

1. Blocked items show orange background
2. Usually affects download stage
3. Worker column shows which account is affected
4. Items automatically resume after cooldown

## Tips and Best Practices

1. **Check Queue Before Starting New Jobs**
   - Avoid duplicating work
   - See current system load
   - Estimate when resources will be available

2. **Monitor Throughput**
   - Rate in header shows system efficiency
   - Low rates may indicate issues
   - High rates show good performance

3. **Use Filters for Large Batches**
   - Filter by stage to focus on specific operations
   - Filter by status to find problems
   - Combine with search for precise results

4. **Watch for Patterns**
   - Multiple failures might indicate configuration issues
   - Blocked downloads suggest rate limiting
   - Slow progress might mean large files

## Troubleshooting

### Queue Not Updating

- Check if auto-refresh is working (watch the clock)
- Try manual refresh with the 🔄 button
- Restart the application if needed

### Missing Items

- Items only appear after being queued for processing
- Completed items remain visible
- Check filters aren't hiding items

### Incorrect Status

- Status updates may lag by a few seconds
- Database updates happen before UI updates
- Manual refresh can force update

## Future Enhancements

The following features are planned for future releases:

- Click to view detailed timeline for each item
- Inline retry/cancel actions
- Export queue snapshot to CSV
- Adjustable refresh interval
- ETA calculations
- Historical analytics

## Keyboard Shortcuts

- **F5** - Manual refresh (when Queue tab is active)
- **Page Up/Down** - Navigate pages
- **Ctrl+F** - Focus search box (coming soon)

## FAQ

**Q: Why is my download stuck at 0%?**
A: The download may be queued or scheduled. Check the status column and worker assignment.

**Q: Can I cancel an in-progress item?**
A: Not yet from the Queue tab. Use the original tab (Transcription/Summarization) to cancel.

**Q: Do completed items disappear?**
A: No, completed items remain visible until you restart the application.

**Q: Why do some items skip stages?**
A: Local files skip the download stage. Some content types may skip certain analysis stages.

**Q: How can I see more details about an item?**
A: Double-click any row to see basic information. A detailed view is coming in a future update.
