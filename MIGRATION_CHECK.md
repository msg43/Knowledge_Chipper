# 🔍 Migration Check Required

**Status:** Upload API is working, but database schema is missing columns

---

## 🎯 What's Working

✅ Device authentication - Device registered successfully
✅ HTTP API endpoint - Accepting requests
✅ Service role key - Environment variable working
✅ Uploader code - Sending data correctly

---

## ❌ What's Missing

The database is missing the `device_id` columns that should have been added by the migration.

**Error messages:**
```
- Episodes upload failed: Could not find the 'device_id' column of 'episodes'
- People upload failed: Could not find the 'claim_id' column of 'people'
- Concepts upload failed: Could not find the 'claim_id' column of 'concepts'
- Jargon upload failed: Could not find the 'claim_id' column of 'jargon'
```

---

## 🔧 Fix: Re-apply Migration

You said you applied the migration earlier, but it looks like it might not have fully executed. Let's verify and re-apply:

### Step 1: Check Supabase

1. Go to https://supabase.com/dashboard
2. Select your GetReceipts project
3. Click "Table Editor" in left sidebar
4. Click on "episodes" table
5. Check if there's a `device_id` column

**If NO `device_id` column:** The migration didn't apply ❌

### Step 2: Re-apply Migration

1. Click "SQL Editor" in left sidebar
2. Click "+ New query"
3. Copy the ENTIRE contents of this file:
   `/Users/matthewgreer/Projects/GetReceipts/database/migrations/001_create_devices_table.sql`

4. Paste into SQL editor
5. Click "Run" (or press Cmd+Enter)

**Expected:** You should see "Success. No rows returned" message

### Step 3: Verify Migration Applied

Go back to Table Editor and check:

**episodes table** should have these NEW columns:
- `device_id` (text)
- `created_by` (uuid)
- `uploaded_at` (timestamptz)

**claims table** should have these NEW columns:
- `device_id` (text)
- `source_claim_id` (text)
- `uploaded_at` (timestamptz)
- `version` (integer)
- `replaces_claim_id` (uuid)

**people, jargon, concepts tables** should have these NEW columns:
- `device_id` (text)
- `source_id` (text)
- `uploaded_at` (timestamptz)

**devices table** should exist with columns:
- `id` (uuid)
- `device_id` (text)
- `device_key_hash` (text)
- `user_id` (uuid, nullable)
- `created_at` (timestamptz)
- `last_seen_at` (timestamptz)
- `device_name` (text, nullable)
- `metadata` (jsonb)

---

## 🧪 After Migration is Applied

Run the test again:

```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper
python3 test_web_canonical_upload.py
```

**Expected:** ✅ All records uploaded successfully!

---

## 💡 Why This Happened

When you said "sql migration complete" earlier, you might have:
- Opened the SQL editor but didn't run it
- Run it in the wrong Supabase project
- Had an error that was dismissed
- The page refreshed before it completed

**The good news:** Everything else is working perfectly! Just need to run that SQL migration.

---

## 📋 Quick Checklist

- [ ] Open Supabase → SQL Editor
- [ ] Copy migration SQL from `database/migrations/001_create_devices_table.sql`
- [ ] Paste and run
- [ ] Verify columns exist in Table Editor
- [ ] Run `python3 test_web_canonical_upload.py`
- [ ] See success! 🎉

---

**Let me know once you've re-run the migration and I'll help you test!**
