# Vercel Environment Variable Setup

**Issue:** The GetReceipts API endpoint returns `supabaseKey is required` error.

**Cause:** The `SUPABASE_SERVICE_ROLE_KEY` environment variable is not set in Vercel.

---

## 🔧 Fix: Add Environment Variable to Vercel

### Step 1: Get Your Supabase Service Role Key

1. Go to https://supabase.com/dashboard
2. Select your GetReceipts project (`sdkxuiqcwlmbpjvjdpkj`)
3. Click "Settings" (gear icon) in the left sidebar
4. Click "API" under Project Settings
5. Scroll down to "Project API keys"
6. Copy the **`service_role`** key (NOT the anon key!)
   - It starts with `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`
   - ⚠️ **Keep this secret!** It bypasses RLS policies

### Step 2: Add to Vercel

1. Go to https://vercel.com/dashboard
2. Select your GetReceipts project
3. Click "Settings" tab
4. Click "Environment Variables" in the left sidebar
5. Click "Add New"
6. Fill in:
   - **Key:** `SUPABASE_SERVICE_ROLE_KEY`
   - **Value:** `<paste the service_role key from Step 1>`
   - **Environments:** Check all (Production, Preview, Development)
7. Click "Save"

### Step 3: Redeploy

After adding the environment variable, you need to redeploy:

**Option A: Trigger via Git Push (Automatic)**
```bash
cd /Users/matthewgreer/Projects/GetReceipts
git commit --allow-empty -m "Trigger redeploy for env vars"
git push origin main
```

**Option B: Manual Redeploy in Vercel Dashboard**
1. Go to "Deployments" tab
2. Click the 3-dot menu on the latest deployment
3. Click "Redeploy"
4. Check "Use existing Build Cache" (optional - faster)
5. Click "Redeploy"

### Step 4: Verify It Works

Wait 1-2 minutes for deployment, then test:

```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper
python3 test_web_canonical_upload.py
```

**Expected Result:** ✅ Upload successful!

---

## 🔍 Alternative: Check Existing Environment Variables

To verify what environment variables are currently set:

1. Go to Vercel Dashboard → GetReceipts project
2. Settings → Environment Variables
3. Look for `SUPABASE_SERVICE_ROLE_KEY`
   - If it's there → Click "Edit" to verify the value is correct
   - If it's missing → Follow Step 2 above

---

## 📋 Required Environment Variables for GetReceipts

Your GetReceipts project needs these variables:

| Variable | Source | Purpose |
|----------|--------|---------|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase Dashboard → API | Public Supabase URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase Dashboard → API | Public anon key (client-side) |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Dashboard → API | Service role key (server-side, bypasses RLS) |

The first two are already set (we used them in testing).
The third one (`SUPABASE_SERVICE_ROLE_KEY`) is what's missing.

---

## 🚨 Security Note

**NEVER commit `SUPABASE_SERVICE_ROLE_KEY` to git!**

- ✅ Add to Vercel environment variables (secure)
- ✅ Add to `.env.local` (git-ignored)
- ❌ NEVER add to `.env.local.example`
- ❌ NEVER commit to git

The service role key bypasses all Row Level Security policies - it's like a master key!

---

## ✅ After Setup

Once the environment variable is set and redeployed, the upload workflow will work:

1. Desktop app uploads via HTTP API
2. API uses `SUPABASE_SERVICE_ROLE_KEY` to bypass RLS
3. Data uploaded with device provenance
4. Claims hidden in desktop (ephemeral)
5. Claims visible in web (canonical)

**Then you can run** `./launch_gui.command` **and test the full workflow!**
