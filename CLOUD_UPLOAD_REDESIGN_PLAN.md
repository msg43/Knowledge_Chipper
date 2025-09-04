# Cloud Upload Redesign Implementation Plan

## Architecture Overview

**Objective**: Transform Cloud Uploads tab from file storage to direct database-to-database upload system.

**Flow**: SQLite Database → Claims Selection → Supabase Database Upload

## Key Requirements

### Authentication & Connection
- **Hardcoded Supabase Credentials**: 
  - URL: `https://sdkxuiqcwlmbpjvjdpkj.supabase.co`
  - Key: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNka3h1aXFjd2xtYnBqdmpkcGtqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU4MTU3MzQsImV4cCI6MjA3MTM5MTczNH0.VoP6yX3GwyVjylgioTGchQYwPQ_K2xQFdHP5ani0vts`
- **User Authentication**: Individual users authenticate with their own username/password  
- **Shared Database**: All users connect to the same Supabase instance

### Data Upload Strategy
- **One-Way Upload**: Desktop → Cloud only (no bidirectional sync)
- **Conflict Resolution**: Local data always overwrites cloud data
- **Upload Scope**: Claims + all associated data (episodes, people, concepts, evidence)
- **Change Tracking**: Only upload claims added/modified since last upload

## Implementation Tasks

### 1. Configuration Changes
- [x] **Hardcode Supabase Connection**: Update CloudConfig with provided credentials
- [x] **Remove Sync Status Tab**: Hide bidirectional sync tab from main window

### 2. Upload State Tracking
- [x] **Add Upload Tracking**: Modify SQLite schema to track upload timestamps per claim
- [x] **Change Detection**: Identify new/modified claims since last upload

### 3. UI Redesign
- [x] **Remove File Controls**: Delete "Root:", "Scan Files", bucket/subfolder controls  
- [x] **SQLite File Browser**: Add database file selection with default to `knowledge_system.db`
- [x] **Warning Dialog**: Show warning when user selects non-default database file
- [x] **Claims List Display**: Replace file table with claims from database

### 4. Claims Selection Interface
- [x] **Auto-Selection**: All new/modified claims selected by default
- [x] **Click-to-Deselect**: Single click to toggle selection (no Ctrl required)
- [x] **Claims Details**: Show claim text, type, tier, timestamps in list/table

### 5. Database Services
- [x] **Claims Reader Service**: Read new/modified claims from SQLite
- [x] **Associated Data Collector**: Gather episodes, people, concepts for selected claims
- [x] **Database Upload Service**: Direct SQLite-to-Supabase upload

### 6. Upload Worker
- [x] **Replace File Worker**: Create database upload worker instead of file upload
- [x] **Progress Tracking**: Show upload progress for database operations
- [x] **Error Handling**: Handle authentication, connection, and data conflicts

### 7. Authentication Integration
- [x] **Retain Auth UI**: Keep existing email/password authentication interface in Cloud Uploads tab
- [x] **Session Management**: Maintain user session for uploads

### 8. Testing & Validation
- [x] **End-to-End Test**: Complete flow from DB selection to successful upload
- [x] **Data Integrity**: Verify all associated data uploads correctly
- [x] **Conflict Handling**: Test overwrite behavior

## Technical Details

### Database Schema Changes
```sql
-- Add upload tracking to claims table
ALTER TABLE claims ADD COLUMN last_uploaded_at TEXT;
ALTER TABLE claims ADD COLUMN upload_status TEXT DEFAULT 'pending';
```

### New UI Components
- **Database File Selector**: Browse button with file dialog
- **Claims Table Widget**: Sortable table with checkboxes
- **Upload Progress**: Progress bar with claim-by-claim status
- **Status Indicators**: Visual feedback for upload success/failure

### Data Upload Flow
1. User selects SQLite database file
2. System queries for new/modified claims
3. Claims displayed with all selected by default
4. User deselects unwanted claims
5. System collects all associated data for selected claims
6. Upload worker pushes data to Supabase with overwrite strategy
7. Update local upload timestamps on success

### Error Handling
- **Database Errors**: Invalid SQLite file, corrupted data
- **Network Errors**: Connection failures, timeouts
- **Authentication Errors**: Invalid credentials, session expiry
- **Conflict Resolution**: Always use local data as source of truth

## Files to Modify

### Core Files
- `src/knowledge_system/config.py` - Hardcode Supabase credentials
- `src/knowledge_system/gui/main_window_pyqt6.py` - Hide Sync Status tab
- `src/knowledge_system/gui/tabs/cloud_uploads_tab.py` - Complete UI redesign

### New Services
- `src/knowledge_system/services/claims_upload_service.py` - Database upload logic
- `src/knowledge_system/services/upload_tracker.py` - Track upload state

### Database Updates
- Migration script for upload tracking columns
- Update existing database service methods

## Success Criteria

✅ **Functional Requirements**:
- Users can select SQLite database files
- Claims list shows only new/modified claims
- All claims selected by default, click-to-deselect works
- Upload pushes claims + associated data to Supabase
- Local data overwrites cloud data on conflicts

✅ **UI Requirements**:
- Clean interface without file/folder controls
- Clear progress indication during uploads
- Intuitive claim selection mechanism
- Proper error messaging and warnings

✅ **Technical Requirements**:
- Hardcoded Supabase connection for all users
- Individual user authentication maintained in Cloud Uploads tab
- Upload state tracking in local database
- Robust error handling and recovery

## Questions Resolved

1. **Database Tables**: Upload claims with all associated data (episodes, people, concepts, evidence)
2. **Data Selection**: Claims from SQLite database, not directory files
3. **File Selection**: Default to `knowledge_system.db`, warn for others
4. **Upload Granularity**: Select individual claims, auto-include associated data
5. **Authentication**: Keep existing email/password UI

## Ready for Implementation

This plan addresses all requirements and clarifications. The implementation will transform the Cloud Uploads tab into a focused database synchronization tool while maintaining user authentication and providing clear feedback throughout the upload process.
