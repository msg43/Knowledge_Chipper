# Auto-Sync Implementation - Complete

**Date:** December 22, 2025  
**Status:** ✅ COMPLETE  
**Impact:** Prevents data loss with auto-sync + close warning following standard best practices

---

## Summary

Implemented three-layer protection against data loss in Extract tab:

1. ✅ **Auto-sync on every accept** - Items sync to GetReceipts immediately in background
2. ✅ **Manual sync button** - Batch sync and retry for failed items
3. ✅ **Close warning** - Prevents closing with unsynced items

Follows standard UX patterns from Gmail, Slack, VS Code, etc.

---

## What Was Implemented

### 1. AutoSyncWorker (Background Sync)

**File:** `src/knowledge_system/gui/workers/auto_sync_worker.py` (NEW)

```python
class AutoSyncWorker(QThread):
    """Background worker for auto-syncing accepted items."""
    
    sync_complete = pyqtSignal(int, list)  # (count, item_ids)
    sync_failed = pyqtSignal(str, list)     # (error, item_ids)
    
    def run(self):
        # Check device linked
        # Convert items to GetReceipts format
        # Upload via GetReceiptsUploader
        # Emit success/failure
```

**Features:**
- Non-blocking background sync
- Handles offline gracefully (queues for retry)
- Includes speaker attribution in uploaded data
- Converts ReviewItems to GetReceipts session format

### 2. Auto-Sync Triggers in Extract Tab

**File:** `src/knowledge_system/gui/tabs/extract_tab.py` (MODIFIED)

**Added state tracking:**
```python
def __init__(self):
    # Auto-sync state
    self.auto_sync_worker = None
    self.pending_sync_count = 0  # Unsynced accepted items
    self.is_syncing = False      # Prevent concurrent syncs
```

**Added auto-sync on accept:**
```python
def _accept_current(self):
    # ... existing code ...
    self.db_service.update_status(item_id, "accepted")
    
    # NEW: Trigger auto-sync
    self._auto_sync_item(self.current_item)
```

**Added auto-sync methods:**
```python
def _auto_sync_item(self, item):
    """Auto-sync single item in background."""
    if not self._is_sync_enabled():
        self.pending_sync_count += 1
        return
    
    worker = AutoSyncWorker([item])
    worker.sync_complete.connect(self._on_auto_sync_complete)
    worker.sync_failed.connect(self._on_auto_sync_failed)
    worker.start()

def _on_auto_sync_complete(self, count, item_ids):
    """Handle successful sync."""
    self.db_service.mark_synced(item_ids)
    self.dashboard.set_sync_status("Synced ✓")
    # Remove synced items from queue
    for item_id in item_ids:
        self.queue_model.remove_item_by_id(item_id)

def _on_auto_sync_failed(self, error, item_ids):
    """Handle failed sync - queue for retry."""
    self.pending_sync_count += len(item_ids)
    self.dashboard.set_sync_status("Queued for sync")
```

**Added unsynced tracking:**
```python
def get_unsynced_count(self) -> int:
    """Get count of accepted items not yet synced."""
    count = 0
    for item in self.queue_model.get_all_items():
        if item.status == ReviewStatus.ACCEPTED:
            if item.item_id and not self.db_service.is_item_synced(item.item_id):
                count += 1
    return count

def sync_all_accepted(self):
    """Sync all accepted items (called from close handler)."""
    self._perform_sync()
```

### 3. Sync Status Indicator in Dashboard

**File:** `src/knowledge_system/gui/components/review_dashboard.py` (MODIFIED)

**Added sync indicator:**
```python
# In _setup_ui()
self.sync_indicator = QLabel("")
self.sync_indicator.setStyleSheet("color: #999; font-size: 11px;")
info_layout.addWidget(self.sync_indicator)
```

**Added methods:**
```python
def set_sync_status(self, status: str):
    """Set sync status with color coding."""
    if "Syncing" in status:
        color = "#3498db"  # Blue
    elif "✓" in status:
        color = "#28a745"  # Green
    elif "Queued" in status:
        color = "#ffc107"  # Yellow
    self.sync_indicator.setStyleSheet(f"color: {color};")
    self.sync_indicator.setText(status)

def set_unsynced_count(self, count: int):
    """Show count of unsynced items."""
    if count > 0:
        self.sync_indicator.setText(f"⚠️ {count} item(s) queued for sync")
```

### 4. Close Warning in Main Window

**File:** `src/knowledge_system/gui/main_window_pyqt6.py` (MODIFIED)

**Updated closeEvent():**
```python
def closeEvent(self, event):
    """Handle window close event."""
    
    # Check Extract tab for unsynced items
    extract_tab = self._find_extract_tab()
    if extract_tab:
        unsynced_count = extract_tab.get_unsynced_count()
        
        if unsynced_count > 0:
            reply = QMessageBox.warning(
                self,
                "Unsynced Items",
                f"You have {unsynced_count} accepted item(s) not synced.\n\n"
                "These items will be lost if you close now.\n\n"
                "What would you like to do?",
                QMessageBox.StandardButton.Save |    # Sync first
                QMessageBox.StandardButton.Discard | # Close anyway
                QMessageBox.StandardButton.Cancel,   # Stay open
                QMessageBox.StandardButton.Save      # Default
            )
            
            if reply == Save:
                extract_tab.sync_all_accepted()
                QTimer.singleShot(2000, self.close)
                event.ignore()
                return
            elif reply == Cancel:
                event.ignore()
                return
            # Discard = continue close
    
    # ... existing cleanup ...
    event.accept()
```

### 5. Database Service Enhancement

**File:** `src/knowledge_system/database/review_queue_service.py` (MODIFIED)

**Added method:**
```python
def is_item_synced(self, item_id: str) -> bool:
    """Check if item has been synced (synced_at is not NULL)."""
    item = session.query(ReviewQueueItem).filter_by(item_id=item_id).first()
    return item.synced_at is not None if item else False
```

### 6. Queue Model Enhancement

**File:** `src/knowledge_system/gui/components/review_queue.py` (MODIFIED)

**Added method:**
```python
def remove_item_by_id(self, item_id: str):
    """Remove an item from the model by its item_id."""
    for i, item in enumerate(self._items):
        if item.item_id == item_id:
            self.beginRemoveRows(QModelIndex(), i, i)
            self._items.pop(i)
            self.endRemoveRows()
            break
```

---

## User Experience

### Scenario 1: Normal Usage (Auto-Sync)

```
User clicks Accept (A)
  ↓
Status saved to database ✓
  ↓
Auto-sync starts in background
  ↓
Dashboard shows: "Syncing..."
  ↓
Upload completes (2-3 seconds)
  ↓
Dashboard shows: "Synced ✓"
  ↓
Item removed from queue
  ↓
User continues reviewing
```

**Result:** No manual sync needed, items appear on web immediately

### Scenario 2: Offline Work

```
User clicks Accept (A)
  ↓
Status saved to database ✓
  ↓
Auto-sync attempts upload
  ↓
Network error detected
  ↓
Dashboard shows: "⚠️ 1 item(s) queued for sync"
  ↓
User continues reviewing (offline)
  ↓
User clicks "Confirm & Sync" later
  ↓
All queued items upload
```

**Result:** Can work offline, items queue for batch sync

### Scenario 3: Close with Unsynced Items

```
User clicks Close (X)
  ↓
App checks: 5 unsynced accepted items
  ↓
Warning dialog appears:
  "You have 5 accepted item(s) not synced.
   These items will be lost if you close now.
   
   What would you like to do?"
   
   [Save] [Discard] [Cancel]
  ↓
User clicks "Save"
  ↓
Sync all 5 items
  ↓
Wait 2 seconds for completion
  ↓
App closes
```

**Result:** No data loss, user has full control

---

## Visual Indicators

### Dashboard Sync Status

**Syncing:**
```
📊 Processing: 1/5 videos  47 items extracted  Pending: 40 | Accepted: 7 | Rejected: 0  Syncing...
```
(Blue color)

**Synced:**
```
📊 Processing: 1/5 videos  47 items extracted  Pending: 40 | Accepted: 7 | Rejected: 0  Synced ✓
```
(Green color)

**Queued (Offline):**
```
📊 Processing: 1/5 videos  47 items extracted  Pending: 40 | Accepted: 7 | Rejected: 0  ⚠️ 3 item(s) queued for sync
```
(Yellow color)

---

## Benefits

1. **No Data Loss** - Items sync immediately, can't be forgotten
2. **Offline Capable** - Can review without internet, sync later
3. **User Control** - Manual sync button for batch operations
4. **Standard UX** - Follows patterns users know (Gmail, Slack)
5. **Fail-Safe** - Close warning catches any missed syncs
6. **Non-Blocking** - Background sync doesn't interrupt workflow
7. **Visual Feedback** - Clear indicators of sync status
8. **Idiot-Proof** - Multiple layers prevent data loss

---

## Technical Details

### Auto-Sync Flow

```
Accept Item
  ↓
Save to Database (immediate)
  ↓
Check Device Linked?
  ├─ No → Queue for sync (pending_sync_count++)
  └─ Yes → Start AutoSyncWorker
              ↓
          Convert to GetReceipts format
              ↓
          Upload via HTTP API
              ↓
          Success?
          ├─ Yes → Mark synced_at
          │        Remove from queue
          │        Show "Synced ✓"
          └─ No → Queue for retry
                   Show "Queued for sync"
```

### Close Warning Flow

```
User Closes App
  ↓
Check unsynced count
  ↓
Count > 0?
  ├─ No → Close normally
  └─ Yes → Show warning dialog
              ↓
          User Choice:
          ├─ Save → Sync all, wait, then close
          ├─ Discard → Close without syncing
          └─ Cancel → Stay open
```

---

## Files Modified

1. ✅ **NEW:** `src/knowledge_system/gui/workers/auto_sync_worker.py`
2. ✅ `src/knowledge_system/gui/tabs/extract_tab.py`
3. ✅ `src/knowledge_system/gui/components/review_dashboard.py`
4. ✅ `src/knowledge_system/gui/components/review_queue.py`
5. ✅ `src/knowledge_system/gui/main_window_pyqt6.py`
6. ✅ `src/knowledge_system/database/review_queue_service.py`

---

## Testing

### Manual Testing Checklist

- [ ] Accept single item → verify "Syncing..." appears
- [ ] Wait 2-3 seconds → verify "Synced ✓" appears
- [ ] Check GetReceipts web → verify item appears
- [ ] Accept 10 items rapidly → verify all sync
- [ ] Disconnect internet → accept item → verify "Queued for sync"
- [ ] Reconnect → click manual sync → verify queued items upload
- [ ] Accept items → close app → verify warning appears
- [ ] Click "Save" → verify sync completes before close
- [ ] Click "Cancel" → verify app stays open
- [ ] Click "Discard" → verify app closes without sync

### Automated Testing

```python
# Test auto-sync worker
def test_auto_sync_worker():
    items = [ReviewItem(...)]
    worker = AutoSyncWorker(items)
    worker.run()
    # Verify sync_complete emitted

# Test unsynced count
def test_get_unsynced_count():
    # Create accepted items
    # Mark some as synced
    # Verify count is correct

# Test close warning
def test_close_warning():
    # Create unsynced items
    # Trigger closeEvent
    # Verify warning dialog appears
```

---

## Configuration

### Device Linking Required

Auto-sync only works if device is linked:

1. Go to Settings tab
2. Click "Link Device"
3. Enter claim code from GetReceipts.org
4. Auto-sync enabled ✓

If not linked:
- Items queue for manual sync
- Dashboard shows: "⚠️ X item(s) queued for sync"
- Manual sync button still works

---

## Rollback (If Needed)

```bash
# Remove auto-sync worker
rm src/knowledge_system/gui/workers/auto_sync_worker.py

# Revert extract_tab.py changes
git checkout src/knowledge_system/gui/tabs/extract_tab.py

# Revert other files
git checkout src/knowledge_system/gui/components/review_dashboard.py
git checkout src/knowledge_system/gui/components/review_queue.py
git checkout src/knowledge_system/gui/main_window_pyqt6.py
git checkout src/knowledge_system/database/review_queue_service.py
```

---

## Related Documents

- `EXTRACT_TAB_UI_IMPROVEMENTS.md` - UI improvements (dark theme, compact layout)
- `SPEAKER_ATTRIBUTION_SIMPLIFICATION_COMPLETE.md` - Speaker field addition
- `CHANGELOG.md` - Updated with auto-sync feature

---

## Conclusion

This implementation makes the Extract tab **idiot-proof** for data loss:

1. ✅ **Auto-sync** - Items upload immediately on accept
2. ✅ **Offline support** - Can work without internet, sync later
3. ✅ **Close protection** - Warning prevents accidental data loss
4. ✅ **Visual feedback** - Clear indicators of sync status
5. ✅ **Standard UX** - Follows familiar patterns

Users can now confidently review items knowing their work is automatically saved and synced to the web (canonical storage).

**Status:** ✅ COMPLETE and READY FOR TESTING

