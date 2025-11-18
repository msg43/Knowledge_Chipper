# Architecture: Web-Canonical with Ephemeral Local

**Branch:** `feature/web-canonical-ephemeral`
**Status:** Experimental (rollback available)
**Inspired by:** [Happy](https://github.com/slopus/happy) - automatic device authentication

---

## Philosophy

**Desktop is a smart processor, Web is the source of truth.**

- Desktop: Extract, process, upload (then forget)
- Web: Store, edit, curate, share
- No sync needed: One-way flow maintains simplicity

---

## How It Works

### 1. Device Authentication (Happy-Style)

**No user sign-in required!** Desktop auto-generates credentials on first launch.

```
First Launch:
  ├─ Generate UUID device_id
  ├─ Generate secure device_key (secrets.token_urlsafe)
  ├─ Store in QSettings (platform-native, encrypted)
  └─ Never ask user for anything!

First Upload:
  ├─ Send credentials in headers (X-Device-ID, X-Device-Key)
  ├─ Backend creates device record (bcrypt-hashed key)
  └─ Device now authenticated forever

Subsequent Uploads:
  ├─ Same headers authenticate automatically
  └─ No tokens, no OAuth, no browser popups!
```

**Files:**
- Desktop: `src/knowledge_system/services/device_auth.py`
- Backend: `/api/knowledge-chipper/device-auth/route.ts`

### 2. Upload Flow

```
Desktop Processing:
  ├─ User drops video/audio
  ├─ Transcribe → Extract claims
  ├─ Store in local SQLite (TEMPORARY)
  └─ Show in "Review Tab" for user review

User Reviews & Uploads:
  ├─ User reviews claims in desktop GUI
  ├─ Clicks "Upload to GetReceipts"
  ├─ Desktop uploads to web API
  └─ Desktop HIDES uploaded claims

Local Database Behavior:
  ├─ Claims marked with hidden=1 after upload
  ├─ get_unuploaded_claims() filters out hidden claims
  ├─ User never sees uploaded claims in desktop again
  └─ Web is now the canonical source!
```

**Files:**
- Desktop: `src/knowledge_system/services/claims_upload_service.py`
- Desktop: `src/knowledge_system/gui/tabs/cloud_uploads_tab.py`
- Backend: `/api/knowledge-chipper/upload/route.ts`

### 3. Reprocessing Workflow

**What happens when user re-processes the same video with a better model?**

```
Desktop Re-Processing:
  ├─ User re-runs extraction on same video
  ├─ New claims extracted (improved quality)
  ├─ Uploaded with same source_id
  └─ Local claims marked hidden after upload

Backend Version Tracking:
  ├─ Detects duplicate source_id from same device
  ├─ Increments version number (v1 → v2)
  ├─ Sets replaces_claim_id pointing to v1
  └─ Both versions preserved in web

Web UI (Future):
  ├─ Shows "You have 2 versions of this claim"
  ├─ User chooses which to keep
  └─ Or merges them manually
```

**Files:**
- Backend: `database/migrations/001_create_devices_table.sql` (version columns)
- Backend: `/api/knowledge-chipper/upload/route.ts` (version detection logic)

### 4. Editing Workflow

**User wants to edit a claim - where do they do it?**

```
❌ NOT in Desktop:
  └─ Desktop doesn't show uploaded claims (hidden=1)

✅ In Web App:
  ├─ User goes to GetReceipts.org
  ├─ Views all uploaded claims
  ├─ Edits directly in browser
  └─ Changes saved to Supabase

Desktop Never Knows:
  └─ Desktop doesn't re-download edits (one-way only)
```

This forces users to the web for curation, which is the goal!

---

## Database Schema

### Desktop (SQLite - Ephemeral)

```sql
CREATE TABLE claims (
  episode_id TEXT,
  claim_id TEXT PRIMARY KEY,
  canonical TEXT,
  -- ... other fields ...
  uploaded_at TEXT,           -- When uploaded to web
  hidden BOOLEAN DEFAULT 0    -- 1 = uploaded, hide from user
);
```

**Behavior:**
- `hidden=0`: Show in Review Tab
- `hidden=1`: Uploaded to web, hide from user
- Claims never deleted (kept for reference) but hidden from view

### Backend (Supabase - Permanent)

```sql
CREATE TABLE devices (
  id UUID PRIMARY KEY,
  device_id TEXT UNIQUE,               -- From desktop
  device_key_hash TEXT,                 -- bcrypt hash
  user_id UUID REFERENCES auth.users,  -- null until claimed
  last_seen_at TIMESTAMPTZ
);

CREATE TABLE claims (
  id UUID PRIMARY KEY,
  device_id TEXT REFERENCES devices,   -- Which device uploaded
  source_claim_id TEXT,                 -- Original claim_id from desktop
  canonical TEXT,
  version INTEGER DEFAULT 1,            -- For reprocessing
  replaces_claim_id UUID,               -- If version > 1
  uploaded_at TIMESTAMPTZ,
  edited_at TIMESTAMPTZ                 -- If user edited in web
);
```

**Provenance:**
- Every claim knows which device uploaded it
- Version tracking for reprocessing
- Edit tracking for web changes

---

## User Experience

### First-Time User

```
1. Install Knowledge_Chipper
2. Drop in video file
3. Claims extracted automatically
4. Review in desktop GUI
5. Click "Upload to GetReceipts"
   └─ Device credentials auto-generated (invisible to user)
6. Claims upload successfully
   └─ Desktop hides them from view
7. User goes to GetReceipts.org to see claims
8. User edits/curates in browser
9. Done! No sync confusion, no conflicts.
```

### Power User (Reprocessing)

```
1. User upgrades LLM model
2. Re-processes old video
3. New, better claims extracted
4. Upload to GetReceipts
   └─ Backend detects: "Version 2 of existing claims"
5. Web shows: "You have 2 versions - which do you prefer?"
6. User chooses/merges in web UI
```

### Settings

Desktop app has simple toggle:

```
[ ✓ ] Enable automatic uploads to GetReceipts
      Device ID: a1b2c3d4...
      [Reset Device Credentials]
```

That's it! No OAuth, no sign-in, no confusion.

---

## API Endpoints

### Device Authentication

**POST** `/api/knowledge-chipper/device-auth`

```typescript
Headers:
  X-Device-ID: "uuid-here"
  X-Device-Key: "secret-here"

Response (New Device):
  {
    "authenticated": true,
    "device_id": "uuid-here",
    "user_id": null,
    "is_new_device": true,
    "message": "Device registered"
  }

Response (Existing Device):
  {
    "authenticated": true,
    "device_id": "uuid-here",
    "user_id": "user-uuid" | null,
    "is_new_device": false,
    "message": "Authenticated"
  }
```

### Upload Claims

**POST** `/api/knowledge-chipper/upload`

```typescript
Headers:
  X-Device-ID: "uuid-here"
  X-Device-Key: "secret-here"

Body:
  {
    "episodes": [...],
    "claims": [...],
    "people": [...],
    "jargon": [...],
    "concepts": [...]
  }

Response:
  {
    "success": true,
    "uploaded": {
      "claims": 42,
      "people": 5,
      // ...
    },
    "device_id": "uuid...",
    "architecture": "web-canonical-ephemeral"
  }
```

---

## Files Modified

### Desktop App

**NEW:**
- `src/knowledge_system/services/device_auth.py` (108 lines)

**MODIFIED:**
- `src/knowledge_system/services/claims_upload_service.py`
  - Added `hidden` column support
  - Added `hide_uploaded_claims()` method
  - Modified `get_unuploaded_claims()` to filter hidden claims

- `src/knowledge_system/gui/tabs/cloud_uploads_tab.py`
  - Simplified UI (removed OAuth)
  - Auto-hide after successful upload
  - Shows device ID for transparency

- `knowledge_chipper_oauth/getreceipts_uploader.py`
  - Uses device headers instead of OAuth
  - Checks `is_enabled()` before upload

**DELETED:**
- `src/knowledge_system/services/supabase_auth.py` (229 lines)
- `src/knowledge_system/services/oauth_callback_server.py` (268 lines)
- `knowledge_chipper_oauth/getreceipts_auth.py` (381 lines)
- `scripts/test_oauth_flow.py` (112 lines)
- **Total removed: 990 lines of OAuth code**

### Backend (GetReceipts)

**NEW:**
- `database/migrations/001_create_devices_table.sql`
- `src/app/api/knowledge-chipper/device-auth/route.ts`

**MODIFIED:**
- `src/app/api/knowledge-chipper/upload/route.ts`
  - Device authentication instead of OAuth
  - Adds `device_id` to all records
  - Version tracking for reprocessing

---

## Comparison: Desktop-Canonical vs Web-Canonical

| Aspect | Desktop-Canonical | Web-Canonical (Ephemeral) |
|--------|-------------------|---------------------------|
| **Local DB** | Permanent, full data | Ephemeral, hidden after upload |
| **Source of Truth** | Desktop SQLite | Web Supabase |
| **Editing** | Desktop or web (conflicts!) | Web only (no conflicts) |
| **Review Tab** | Shows all claims | Shows only un-uploaded claims |
| **Reprocessing** | User manually manages | Version tracking automatic |
| **Sync** | Would need two-way sync | No sync needed (one-way) |
| **Complexity** | Medium | Low |
| **User Confusion** | "Which is newer?" | "Web is always current" |

---

## Rollback Instructions

To go back to desktop-canonical architecture:

```bash
# Restore desktop-canonical implementation
git checkout feature/desktop-canonical

# Or compare the two branches
git diff feature/desktop-canonical feature/web-canonical-ephemeral
```

---

## Future Enhancements

**Device Claiming (Web UI):**
- Allow users to "claim" devices through web interface
- Associate device_id with user account
- View all devices, rename them ("My MacBook Pro")

**Web Editing UI:**
- Claims editor with rich text
- People merger (dedupe "Elon Musk" variants)
- Jargon definitions
- Concept relationship graph

**Version Management:**
- Compare v1 vs v2 side-by-side
- Merge claims from different versions
- Keep best parts of each

---

## Credits

Inspired by [Happy](https://github.com/slopus/happy) by @slopus - automatic device authentication without user onboarding.

**Built with:**
- Claude Code (claude.ai/code)
- Happy (happy.engineering)

**Architecture Decision:** November 17, 2025
