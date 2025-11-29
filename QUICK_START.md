# 🚀 Quick Start - 3 Steps to Test

## Step 1: Add Vercel Environment Variable (5 min)

**Get your Supabase service role key:**
1. https://supabase.com/dashboard → Your GetReceipts project
2. Settings → API
3. Copy the **`service_role`** secret key (long string starting with `eyJ...`)

**Add to Vercel:**
1. https://vercel.com/dashboard → Your GetReceipts project
2. Settings → Environment Variables
3. Add: `SUPABASE_SERVICE_ROLE_KEY` = `<paste key here>`
4. Check all environments (Production, Preview, Development)
5. Save

**Redeploy:**
```bash
cd /Users/matthewgreer/Projects/GetReceipts
git commit --allow-empty -m "Trigger redeploy"
git push origin main
```

Wait 2 minutes for deployment.

---

## Step 2: Test Upload (1 min)

```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper
python3 test_web_canonical_upload.py
```

**Expected:**
```
✅ Upload completed successfully!
```

If you see this → proceed to Step 3!

If you see errors → check Vercel deployment logs or ping me.

---

## Step 3: Test Full GUI Workflow (10 min)

```bash
./launch_gui.command
```

**Test Checklist:**
- [ ] Process a short test video/audio
- [ ] Go to Review tab → see claims
- [ ] Go to Cloud Uploads tab → upload claims
- [ ] **KEY TEST:** Go back to Review tab → claims should be GONE
- [ ] Open Supabase → claims should be there

**Device ID:** `be114cb7-ed43-44b4-8c64-e66b14ea7576`

---

## ✅ Success = Claims Disappear from Desktop

If uploaded claims **vanish** from the Review tab after upload, the ephemeral architecture is working! 🎉

Then check Supabase to verify they're in the web database.

---

## 📚 More Info

- **Vercel setup details:** `VERCEL_ENV_SETUP.md`
- **Complete testing guide:** `READY_TO_TEST.md`
- **Architecture docs:** `ARCHITECTURE_WEB_CANONICAL.md`
- **Test results:** `WEB_CANONICAL_TESTING_RESULTS.md`

---

**That's it!** Just add the env var and test. Let me know how it goes! 🚀
