# Sunrise Tab Sorting - Visual Guide

## How to Use

### Step 1: Navigate to Sunrise Tab
1. Launch Knowledge Chipper
2. Click on the "Sunrise" (Summarization) tab
3. Select "Use Database" radio button

### Step 2: View the Enhanced Table
You'll now see 6 columns:

```
┌────────┬─────────────────────────────┬──────────┬─────────────┬─────────────┬──────────────────┐
│ Select │ Title                       │ Duration │ Has Summary │ Token Count │ Date Added       │
├────────┼─────────────────────────────┼──────────┼─────────────┼─────────────┼──────────────────┤
│   ☐    │ Example Video 1             │ 45:23    │ ✓           │ ~12,345     │ 2025-11-07 14:30 │
│   ☐    │ Another Great Episode       │ 1:23:45  │ ✗           │ ~25,678     │ 2025-11-06 09:15 │
│   ☐    │ Short Clip                  │ 5:12     │ ✓           │ ~1,234      │ 2025-11-05 16:45 │
└────────┴─────────────────────────────┴──────────┴─────────────┴─────────────┴──────────────────┘
```

### Step 3: Sort by Any Column
Click on any column header to sort:

#### Sort by Title (Alphabetical)
- Click "Title" header → A-Z
- Click again → Z-A

#### Sort by Duration (Shortest/Longest)
- Click "Duration" header → Shortest first
- Click again → Longest first

#### Sort by Has Summary (Status)
- Click "Has Summary" header → ✓ items first
- Click again → ✗ items first

#### Sort by Token Count (Size)
- Click "Token Count" header → Smallest first
- Click again → Largest first

#### Sort by Date Added (Newest/Oldest)
- Click "Date Added" header → Oldest first
- Click again → Newest first

## Common Use Cases

### Find Recently Added Sources
1. Click "Date Added" column header twice
2. Newest sources appear at the top
3. Great for finding what you just added

### Find Long Videos to Summarize
1. Click "Duration" column header twice
2. Longest videos appear at the top
3. Useful for planning summarization batches

### Find Unsummarized Content
1. Click "Has Summary" column header
2. Items without summaries (✗) appear at the top
3. Quick way to find work that needs to be done

### Find Large Transcripts
1. Click "Token Count" column header twice
2. Largest transcripts appear at the top
3. Helps identify content that may need special handling

## Technical Notes

- Sorting is **client-side** (instant, no database queries)
- Sorting uses **proper data types** (not just text):
  - Duration sorts by seconds (not by text)
  - Token Count sorts by number (not by formatted string)
  - Date Added sorts by timestamp (not by formatted date)
- Checkboxes remain with their rows when sorting
- Search filter works independently of sorting
- Sorting state persists while the tab is open

## Tips

1. **Combine with Search**: Use the search box to filter, then sort the results
2. **Multiple Sorts**: Sort by one column, then another to create sub-sorts
3. **Visual Indicators**: The sorted column header shows an arrow indicator
4. **Performance**: Sorting is instant even with hundreds of entries

## Example Workflows

### Workflow 1: Process Recent Additions
```
1. Click "Date Added" twice (newest first)
2. Select top 10 items
3. Click "Start Summarization"
```

### Workflow 2: Tackle Big Content First
```
1. Click "Token Count" twice (largest first)
2. Click "Has Summary" once (✗ first)
3. Select items without summaries
4. Process in batches
```

### Workflow 3: Quick Wins
```
1. Click "Duration" once (shortest first)
2. Click "Has Summary" once (✗ first)
3. Select short videos without summaries
4. Process quickly for fast progress
```
