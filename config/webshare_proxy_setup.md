# ⚠️ DEPRECATED: WebShare Proxy Setup

**This documentation is deprecated and will be removed in a future version.**

## 🔄 Migration Notice

**WebShare proxy support is being replaced with Bright Data integration** for improved cost efficiency and reliability.

### Why the Change?

- ✅ **Pay-per-request** instead of monthly subscriptions
- ✅ **Better reliability** with Bright Data's YouTube API Scrapers
- ✅ **Direct JSON responses** instead of proxy scraping
- ✅ **Built-in IP rotation** and session management
- ✅ **Lower costs** for typical usage patterns

### 📚 New Documentation

**Please use the new Bright Data setup guide:**
- **Setup Guide**: `config/bright_data_setup.md`
- **Configuration**: Use the GUI "API Keys" tab to enter your Bright Data API key

### 🔄 Backward Compatibility

WebShare credentials are still supported for backward compatibility, but Bright Data will be used when configured:

1. **Bright Data API Key** (preferred) - pay per request
2. **WebShare credentials** (fallback) - monthly subscription

### 📋 Migration Steps

1. **Get Bright Data API Key**: Sign up at [brightdata.com](https://brightdata.com/)
2. **Configure in GUI**: Go to API Keys tab → Enter Bright Data API Key
3. **Test**: Process a video to verify Bright Data integration works
4. **Optional**: Remove WebShare credentials once Bright Data is working

---

## Legacy WebShare Instructions (Deprecated)

> **⚠️ WARNING**: This section is maintained for backward compatibility only.
> New users should use Bright Data instead.

### 1. Get Webshare Account

1. Go to [Webshare.io](https://www.webshare.io/)
2. Sign up for an account
3. Choose a residential proxy plan with rotating endpoints

### 2. Get Your Credentials

From your Webshare dashboard, you'll need:

- **Username**: Your proxy username (should end with `-rotate` for automatic rotation)
- **Password**: Your proxy password 

### 3. Configure in Knowledge System

**Option 1: Using the GUI (Recommended)**
1. Open Knowledge System
2. Go to "API Keys" tab
3. Enter your WebShare Username and Password
4. Save settings

**Option 2: Environment Variables**
```bash
export WEBSHARE_USERNAME="your_username_here"
export WEBSHARE_PASSWORD="your_password_here"
```

**Option 3: Configuration File**
```yaml
# config/credentials.yaml
api_keys:
  webshare_username: "your_username_here"
  webshare_password: "your_password_here"
```

### 4. Test Your Setup

Run a test video to verify WebShare proxy is working:

```bash
knowledge-system process "https://youtube.com/watch?v=dQw4w9WgXcQ" --transcribe
```

---

**🔔 Reminder**: This setup method is deprecated. Please migrate to Bright Data for better performance and cost efficiency. See `bright_data_setup.md` for the new setup process.
