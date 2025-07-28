# Configuration Directory

This directory contains configuration files for the Knowledge Workflow system.

## 🔐 Credential Setup

### Option 1: Use the GUI (Recommended)
1. Open the Knowledge Workflow application
2. Go to the **"API Keys"** tab
3. Enter your credentials:
   - **WebShare Username & Password** (required for YouTube processing)
   - **OpenAI API Key** (required for GPT summarization)
   - **Anthropic API Key** (required for Claude summarization)
   - **HuggingFace Token** (required for speaker diarization)
4. Click **"💾 Save API Keys"**
5. Credentials will be automatically saved to `config/credentials.yaml`

### Option 2: Manual Setup
1. Copy `credentials.example.yaml` to `credentials.yaml`:
   ```bash
   cp config/credentials.example.yaml config/credentials.yaml
   ```
2. Edit `config/credentials.yaml` with your actual API keys
3. The file will be automatically loaded when the application starts

## 🔒 Security Features

- ✅ **`credentials.yaml` is excluded from git** - Your keys will never be committed
- ✅ **File permissions set to 600** - Only you can read the credentials file
- ✅ **Automatic loading** - Credentials persist across application restarts
- ✅ **Environment variable fallback** - Can still use environment variables if preferred

## 📁 File Structure

```
config/
├── credentials.example.yaml    # Template (safe to commit)
├── credentials.yaml           # Your actual credentials (git-ignored)
├── settings.yaml              # Performance settings (optional)
└── README.md                  # This file
```

## 🚨 Important Security Notes

- **Never commit `credentials.yaml`** to version control
- **Keep your API keys private** - don't share them
- **Regularly rotate your keys** for security
- **Use the minimum required permissions** for each API key

## 🔗 Where to Get API Keys

- **WebShare Proxy**: https://www.webshare.io/
- **OpenAI API**: https://platform.openai.com/api-keys
- **Anthropic API**: https://console.anthropic.com/
- **HuggingFace Token**: https://huggingface.co/settings/tokens 