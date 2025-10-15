# Deleting Claims from the Review Tab

## Overview

The Review Tab allows you to permanently delete claims from the database. This is useful for removing incorrect, duplicate, or unwanted claims that were extracted during the HCE pipeline processing.

## How to Delete Claims

### Step 1: Navigate to the Review Tab

Open the Knowledge Chipper application and click on the "Review" tab to view all extracted claims.

### Step 2: Select Claims to Delete

Click on one or more claims in the table to select them:

- **Single Selection**: Click on a row to select it
- **Multiple Selection**: Hold Ctrl (Windows/Linux) or Cmd (Mac) and click on multiple rows
- **Range Selection**: Click on a row, hold Shift, and click on another row to select all rows in between

### Step 3: Click the Delete Button

Once you have selected the claims you want to delete, click the "🗑️ Delete Selected" button at the bottom of the screen.

**Note**: The delete button is only enabled when you have at least one claim selected.

### Step 4: Confirm Deletion

A confirmation dialog will appear asking you to confirm the deletion:

```
Are you sure you want to permanently delete X claim(s)?

This action cannot be undone.
```

- Click "Yes" to proceed with the deletion
- Click "No" to cancel and keep the claims

### Step 5: Deletion Complete

After successful deletion, you will see a confirmation message:

```
Successfully deleted X claim(s) from the database.
```

The table will automatically refresh to show the updated list of claims.

## Important Notes

⚠️ **Warning**: Deletion is permanent and cannot be undone. Make sure you want to delete the claims before confirming.

### What Gets Deleted

When you delete a claim, the following related data is also automatically removed:

- **Evidence Spans**: All evidence supporting the claim
- **Relations**: Any relationships this claim has with other claims (supports, contradicts, etc.)

### What Stays

The following data is NOT deleted:

- **Episode**: The episode that the claim came from remains in the database
- **Segments**: The transcript segments remain unchanged
- **Other Claims**: Other claims from the same episode are not affected

## Use Cases

### Removing Duplicate Claims

If the HCE pipeline extracted the same claim multiple times, you can select and delete the duplicates.

### Removing Incorrect Claims

If a claim was incorrectly extracted or doesn't make sense, you can remove it from the database.

### Cleaning Up Test Data

During testing or development, you may want to remove test claims from the database.

### Filtering by Episode

You can use the episode filter dropdown to view claims from a specific episode, making it easier to find and delete claims from that episode.

## Tips

1. **Review Before Deleting**: Double-check the claims you've selected before clicking delete
2. **Use Episode Filter**: Filter by episode to focus on specific content
3. **Export First**: Consider exporting claims to CSV or JSON before deleting them, in case you need to reference them later
4. **Delete in Batches**: For large deletions, consider deleting in smaller batches to avoid performance issues

## Troubleshooting

### Delete Button is Disabled

- Make sure you have selected at least one claim
- Try clicking directly on a row to ensure it's selected

### Deletion Failed

If you see an error message, check the logs for more details. Common causes:
- Database connection issues
- Insufficient permissions
- Database corruption

### Claims Reappear After Deletion

If claims reappear after deletion, it may be because:
- The episode was reprocessed through the HCE pipeline
- Another user or process added the claims back
- The database was restored from a backup

## Related Features

- **Claim Editing**: Double-click on a claim to edit its properties
- **Export**: Export claims to CSV, Markdown, or JSON before deleting
- **Episode Filter**: Filter claims by episode for easier management

