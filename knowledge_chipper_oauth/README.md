# Knowledge_Chipper OAuth Integration Package

🔐 **Complete OAuth integration for uploading Knowledge_Chipper data to GetReceipts.org**

This package provides everything you need to add secure user authentication and data upload capabilities to Knowledge_Chipper, allowing users to seamlessly share their extracted claims and knowledge artifacts with the GetReceipts.org community.

## 📦 **What's Included**

| File | Purpose |
|------|---------|
| `getreceipts_auth.py` | OAuth authentication handler |
| `getreceipts_uploader.py` | Data upload manager with Supabase integration |
| `getreceipts_config.py` | Configuration management (dev/prod) |
| `integration_example.py` | Complete working example |
| `requirements_oauth.txt` | Python dependencies |
| `README.md` | This documentation |

## 🚀 **Quick Start**

### 1. **Install Dependencies**
```bash
cd /path/to/your/knowledge_chipper
pip install -r requirements_oauth.txt
```

### 2. **Configure Credentials**
Edit `getreceipts_config.py`:
```python
DEVELOPMENT = {
    'base_url': 'http://localhost:3000',
    'supabase_url': 'https://YOUR-ACTUAL-PROJECT.supabase.co',  # ← Update this
    'supabase_anon_key': 'YOUR-ACTUAL-ANON-KEY-HERE'            # ← Update this
}
```

### 3. **Test Integration**
```bash
python integration_example.py
```

### 4. **Add to Your Code**
```python
from integration_example import upload_to_getreceipts

# After your HCE processing:
results = upload_to_getreceipts(session_data)
```

## 🔐 **How OAuth Works**

```
1. User runs Knowledge_Chipper with upload option
2. Browser opens to GetReceipts.org OAuth page
3. User signs in or creates account
4. Browser redirects back with access token
5. Knowledge_Chipper uploads data with user attribution
6. All uploads are linked to the authenticated user
```

## 📊 **Data Flow**

```
Knowledge_Chipper HCE Data → OAuth Authentication → Supabase Upload
                                      ↓
episodes, claims, evidence, people, jargon, concepts, relations
                                      ↓
            GetReceipts.org Database (with user attribution)
```

## 🔧 **Integration Options**

### **Option A: Manual Upload (Recommended for Testing)**
```python
from getreceipts_uploader import GetReceiptsUploader

uploader = GetReceiptsUploader()
uploader.authenticate()  # Opens browser
results = uploader.upload_session_data(your_data)
```

### **Option B: Automatic Upload After Processing**
```python
from integration_example import upload_to_getreceipts

def process_with_auto_upload(video_url):
    # Your existing processing
    session_data = process_video(video_url)
    
    # Auto-upload to GetReceipts
    try:
        upload_to_getreceipts(session_data)
        print("✅ Uploaded to GetReceipts.org!")
    except Exception as e:
        print(f"Upload failed: {e}")
    
    return session_data
```

### **Option C: Batch Upload**
```python
def batch_upload_sessions(session_list):
    uploader = GetReceiptsUploader()
    uploader.authenticate()  # Auth once for all uploads
    
    for session_data in session_list:
        try:
            uploader.upload_session_data(session_data)
            print(f"✅ Uploaded session")
        except Exception as e:
            print(f"❌ Failed: {e}")
```

## 📁 **File Documentation**

### **`getreceipts_auth.py`**
Handles the complete OAuth flow:
- Opens browser to GetReceipts.org
- Starts local callback server on port 8080
- Captures access tokens and user info
- Provides authentication status checking

**Key Methods:**
- `authenticate()` - Start OAuth flow
- `is_authenticated()` - Check if user is logged in
- `get_auth_headers()` - Get headers for API calls

### **`getreceipts_uploader.py`**
Manages data transformation and upload:
- Converts HCE format to GetReceipts schema
- Handles all data types (episodes → claims → evidence → artifacts)
- Uses Supabase client with user attribution
- Provides detailed upload progress and error handling

**Key Methods:**
- `authenticate()` - Start OAuth (uses auth module)
- `upload_session_data(data)` - Upload complete session
- Individual `_upload_*()` methods for each data type

### **`getreceipts_config.py`**
Configuration management:
- Development vs Production settings
- Environment variable override support
- Configuration validation
- Easy switching between environments

**Key Functions:**
- `get_config()` - Get current configuration
- `set_production()` - Switch to production URLs
- `validate_config()` - Check if setup is complete

### **`integration_example.py`**
Complete working example:
- Demonstrates authentication flow
- Shows data upload process
- Includes error handling and progress reporting
- Provides reusable `upload_to_getreceipts()` function

## 🌍 **Environment Configuration**

### **Development (Default)**
- GetReceipts.org: `http://localhost:3000`
- OAuth callback: `http://localhost:8080/auth/callback`
- Your local Supabase development database

### **Production**
```python
from getreceipts_config import set_production
set_production()
```
- GetReceipts.org: `https://skipthepodcast.com`
- OAuth callback: `http://localhost:8080/auth/callback`
- Production Supabase database

### **Environment Variables (Optional)**
```bash
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_ANON_KEY="your-anon-key"
export GETRECEIPTS_BASE_URL="http://localhost:3000"
export OAUTH_CALLBACK_PORT="8080"
```

## 🗄️ **Data Mapping**

The uploader automatically transforms your HCE data:

| Knowledge_Chipper Table | GetReceipts Table | Key Transformations |
|-------------------------|-------------------|-------------------|
| `episodes` | `episodes` | Direct mapping + source type detection |
| `claims` | `claims` | Parse `scores_json` → individual score columns |
| `evidence_spans` | `evidence` | Map timestamps, link to claims/episodes |
| `people` | `people` | Entity mentions with confidence scores |
| `jargon` | `jargon` | Technical terms with definitions |
| `concepts` | `mental_models` | Conceptual frameworks with relationships |
| `relations` | `claim_relationships` | Claim interconnections with strength |

## 🐛 **Troubleshooting**

### **"Authentication timeout"**
- Ensure GetReceipts.org is running on the expected URL
- Check that browser popup isn't blocked
- Try clearing browser cache and cookies

### **"Configuration incomplete"**
- Update `getreceipts_config.py` with real Supabase credentials
- Get credentials from GetReceipts team
- Run `python getreceipts_config.py` for setup instructions

### **"Upload failed" errors**
- Verify authentication completed successfully
- Check internet connection to Supabase
- Ensure your session data format matches HCE structure
- Check Supabase dashboard for detailed error logs

### **"Port already in use"**
- Change `callback_port` in configuration
- Kill any processes using port 8080: `lsof -ti:8080 | xargs kill`

### **"Missing claim references"**
- Ensure claims are uploaded before evidence/artifacts
- Check that `claim_id` and `episode_id` values match
- Verify foreign key relationships in your data

## 📞 **Getting Help**

1. **Test with the example first**: `python integration_example.py`
2. **Check configuration**: `python getreceipts_config.py`
3. **Verify GetReceipts.org is running** on the expected URL
4. **Check browser developer console** for OAuth errors
5. **Review Supabase logs** in the dashboard for detailed errors

## 🔄 **Development Workflow**

1. **Setup**: Configure credentials in `getreceipts_config.py`
2. **Test**: Run `integration_example.py` to verify everything works
3. **Integrate**: Add `upload_to_getreceipts()` to your processing pipeline
4. **Development**: Use default configuration for local testing
5. **Production**: Call `set_production()` for live deployment

## 🎯 **Production Deployment**

When deploying Knowledge_Chipper with GetReceipts integration:

1. **Update configuration** for production URLs
2. **Set environment variables** with production credentials
3. **Test OAuth flow** with production GetReceipts.org
4. **Monitor uploads** through Supabase dashboard
5. **Handle errors gracefully** with try/catch blocks

## 📈 **Next Steps**

1. **Install this package** in your Knowledge_Chipper project
2. **Configure your credentials** 
3. **Test with sample data** using the example
4. **Integrate with your main processing** loop
5. **Deploy to production** when ready

This OAuth integration enables secure, user-attributed data sharing between Knowledge_Chipper and GetReceipts.org, creating a seamless pipeline from content processing to community knowledge sharing! 🚀

---

**Questions?** Check the troubleshooting section or contact the GetReceipts.org team.
