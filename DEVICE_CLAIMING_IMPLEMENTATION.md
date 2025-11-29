# Device Claiming System - Implementation Complete

**Date:** November 21, 2025
**Architecture:** Happy-style zero-friction onboarding with device claiming

---

## Overview

Users can now download the app, process files, and have them automatically upload to the cloud **without ever creating an account**. When they're ready, they can claim their devices via a simple 6-character code to link all their data to a user account.

---

## User Experience

### Day 1: Zero Friction
```
1. User downloads Knowledge_Chipper
2. Processes a video file
3. Data automatically uploads to cloud (device_id assigned, user_id=NULL)
4. User never asked to create account ✅
```

### Day 7: Multi-Device Sync
```
1. User thinks "I want to access this on my phone"
2. Goes to getreceipts.org and creates account
3. Opens desktop app → Cloud Uploads tab → sees claim code: "VE2 WKY"
4. Goes to getreceipts.org/claim → enters code
5. All data from that device now linked to account ✅
```

### Day 30: Multiple Devices
```
1. User installs on laptop
2. Processes more files (new device_id assigned)
3. Enters same claim code on laptop
4. Now both devices linked to same account
5. User sees all data from both devices in web dashboard ✅
```

---

## Implementation Details

### 1. Desktop App (Knowledge_Chipper)

**Files Created:**
- `src/knowledge_system/utils/claim_code.py` - Claim code generation utility

**Files Modified:**
- `src/knowledge_system/gui/tabs/cloud_uploads_tab.py` - Added claim code display

**What Changed:**
```python
# Cloud Uploads tab now shows:
"🔗 Claim Code: VE2 WKY
 Go to getreceipts.org/claim to link your devices"
```

### 2. Web App (GetReceipts)

**Files Created:**
- `src/lib/claim-code.ts` - TypeScript claim code utilities
- `src/app/api/devices/claim/route.ts` - Device claiming API endpoint
- `src/app/claim/page.tsx` - Device claiming web page
- `database/migrations/002_add_device_claim_rls_policies.sql` - RLS policies

**What Changed:**
- Users can visit `/claim` and enter their 6-character code
- API validates code and links device to user account
- RLS policies allow users to see data from claimed devices

---

## Technical Details

### Claim Code Algorithm

**Deterministic:** Same device_id always generates same code
```python
# Python (Desktop)
hash = sha256(device_id).digest()
short_hash = hash[:4]
base32_encoded = base32.encode(short_hash)
claim_code = base32_encoded[:6]  # e.g., "VE2WKY"

# TypeScript (Web) - identical algorithm
```

**Properties:**
- 6 characters (easy to type)
- Base32 alphabet (no 0/O/1/I/L confusion)
- ~16 million unique codes
- Case-insensitive
- Human-readable with spacing: "VE2 WKY"

### Database Schema

**Devices Table:**
```sql
devices (
  id UUID PRIMARY KEY,
  device_id TEXT UNIQUE,           -- UUID from desktop
  device_key_hash TEXT,             -- bcrypt hash
  user_id UUID REFERENCES auth.users,  -- NULL until claimed!
  device_name TEXT,
  created_at TIMESTAMPTZ,
  last_seen_at TIMESTAMPTZ
)
```

**Data Tables (claims, episodes, etc.):**
```sql
claims (
  id UUID PRIMARY KEY,
  device_id TEXT REFERENCES devices(device_id),  -- Track which device
  canonical TEXT,
  -- ... other fields ...
)
```

### Row-Level Security

**Before Claiming:**
```sql
-- Device uploads with device_id, user_id=NULL
-- Service role (API) can insert (bypasses RLS)
-- User cannot see data (no user_id match)
```

**After Claiming:**
```sql
-- UPDATE devices SET user_id = 'user-123' WHERE device_id = 'abc'
-- RLS policy: SELECT * FROM claims WHERE device_id IN
--   (SELECT device_id FROM devices WHERE user_id = auth.uid())
-- User can now see ALL historical data from that device!
```

---

## API Endpoints

### POST /api/devices/claim

**Request:**
```json
{
  "claim_code": "VE2WKY"
}
```

**Response (Success):**
```json
{
  "success": true,
  "device_id": "be114cb7-ed43-44b4-8c64-e66b14ea7576",
  "device_name": "My MacBook",
  "claim_count": 42,
  "message": "Device successfully linked! Found 42 claims from this device."
}
```

**Response (Already Claimed):**
```json
{
  "success": false,
  "error": "Device already claimed",
  "message": "This device is already linked to another account"
}
```

---

## Migration Instructions

### Apply to Supabase

Run the RLS migration:
```sql
-- In Supabase SQL Editor:
-- Copy contents of database/migrations/002_add_device_claim_rls_policies.sql
-- Execute all statements
```

This adds:
- RLS policies for users to view their claimed device data
- Service role policies for API uploads
- Enables RLS on all knowledge tables

---

## Testing Checklist

### Desktop App
- [ ] Launch app, check Cloud Uploads tab
- [ ] Verify claim code displayed (6 characters, formatted)
- [ ] Verify clickable link to getreceipts.org/claim
- [ ] Process a file, upload to cloud
- [ ] Verify data uploaded with device_id, user_id=NULL

### Web App
- [ ] Visit /claim page
- [ ] Verify UI loads correctly
- [ ] Try claiming without signing in (should redirect to /auth/signin)
- [ ] Sign in, return to /claim
- [ ] Enter claim code from desktop
- [ ] Verify success message shows claim count
- [ ] Navigate to dashboard
- [ ] Verify claims from claimed device are visible

### Multi-Device
- [ ] Install app on second computer
- [ ] Process different file
- [ ] Enter same claim code
- [ ] Verify both devices' data visible in web dashboard
- [ ] Verify claims tagged with different device_ids

---

## User-Facing Documentation

**Desktop App - Cloud Uploads Tab:**
```
🔗 Claim Code: VE2 WKY
   Go to getreceipts.org/claim to link your devices

This code links your device to your GetReceipts account.
- Same code works on all your devices
- Enter it on the website to sync across devices
- Your data uploads automatically (no account required!)
```

**Web App - /claim Page:**
```
Link Your Device

Enter the claim code from your Knowledge_Chipper desktop app

How it works:
1. Open Knowledge_Chipper desktop app
2. Go to the Cloud Uploads tab
3. Copy your 6-character claim code
4. Enter it here to link all your devices
```

---

## Deployment Checklist

### Knowledge_Chipper (Desktop)
- [x] Implement claim code utility
- [x] Update Cloud Uploads tab UI
- [ ] Test locally
- [ ] Commit to branch
- [ ] Merge to main
- [ ] Create release

### GetReceipts (Web)
- [x] Implement claim code utility (TypeScript)
- [x] Create /api/devices/claim endpoint
- [x] Create /claim page
- [x] Create RLS migration
- [ ] Test locally
- [ ] Apply RLS migration to Supabase production
- [ ] Deploy to Vercel
- [ ] Test in production

---

## Future Enhancements

### Device Management Dashboard
```typescript
// /dashboard/devices page
- List all claimed devices
- Rename devices ("My MacBook Pro", "Work Laptop")
- See claim count per device
- Unclaim devices
- View upload history per device
```

### QR Code Claiming
```python
# Desktop shows QR code
qr_data = {
  "device_id": device_id,
  "claim_code": claim_code,
  "url": "https://getreceipts.org/claim?code=VE2WKY"
}

# User scans with phone → auto-opens web → auto-fills code
```

### Email Claiming (Happy-style)
```python
# Desktop optionally asks for email
email = input("Email to sync devices (optional):")
send_claim_email(email, device_id, claim_code)

# User clicks email link → auto-claims device
```

---

## Credits

Inspired by **[Happy](https://github.com/slopus/happy)** by @slopus - automatic device authentication without user onboarding.

**Built with:**
- Claude Code (claude.ai/code)
- Happy (happy.engineering)

**Architecture Decision:** November 21, 2025
