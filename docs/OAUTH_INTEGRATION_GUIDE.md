# OAuth Integration Guide - GetReceipts Authentication

This guide explains how the Knowledge_Chipper OAuth integration with GetReceipts works and how to use it.

## Overview

Knowledge_Chipper now supports OAuth authentication through GetReceipts, allowing users to securely sign in and upload their claims data to a shared Supabase database.

## How It Works

### Authentication Flow

1. **User clicks "Sign In with GetReceipts"** in the Cloud Uploads tab
2. **Local callback server starts** on `localhost:8080`
3. **Browser opens** to GetReceipts OAuth URL:
   ```
   https://getreceipts.org/auth/signin?redirect_to=knowledge_chipper&return_url=http://localhost:8080/auth/callback
   ```
4. **User authenticates** on GetReceipts (trusted domain)
5. **GetReceipts redirects** back with tokens:
   ```
   http://localhost:8080/auth/callback?access_token=<jwt>&refresh_token=<refresh>&user_id=<uuid>
   ```
6. **Knowledge_Chipper receives tokens** and sets up Supabase session
7. **User is authenticated** and can upload claims data

### Security Features

- ✅ **No password storage** - OAuth handles all authentication
- ✅ **Secure token exchange** - JWT tokens from trusted provider
- ✅ **Local callback server** - Handles OAuth redirect securely
- ✅ **Automatic session setup** - Supabase session configured with received tokens
- ✅ **User isolation** - RLS policies ensure users only see their own data

## Using the OAuth Flow

### In the GUI

1. **Open Knowledge_Chipper**
2. **Go to Cloud Uploads tab**
3. **Click "🌐 Sign In with GetReceipts"**
4. **Wait for browser to open** (progress dialog will show)
5. **Complete authentication** on GetReceipts
6. **Return to app** - you'll see "✅ Signed In"
7. **Upload your claims** using the upload controls

### Legacy Authentication

If you prefer direct email/password authentication (not recommended for production):

1. **Click "▶ Advanced: Direct Email/Password Sign-In"** to expand
2. **Enter email and password**
3. **Click "Sign In" or "Sign Up"**

## Technical Components

### OAuth Callback Server

Located in `src/knowledge_system/services/oauth_callback_server.py`:

- **HTTP Server**: Runs on `localhost:8080`
- **Callback Handler**: Processes OAuth redirect
- **Token Extraction**: Parses tokens from URL parameters
- **User Feedback**: Shows success/error pages in browser
- **Automatic Cleanup**: Stops server after callback received

### Supabase Auth Service

Enhanced in `src/knowledge_system/services/supabase_auth.py`:

- **OAuth Flow**: `sign_up_with_oauth()` method
- **Token Handling**: `set_session_from_tokens()` method
- **Session Management**: Standard Supabase auth methods
- **Browser Integration**: Opens GetReceipts OAuth URL

### Cloud Uploads UI

Updated in `src/knowledge_system/gui/tabs/cloud_uploads_tab.py`:

- **OAuth Button**: Primary authentication method
- **Progress Dialog**: Shows OAuth flow status
- **Legacy Auth**: Collapsible email/password section
- **Status Updates**: Real-time authentication state

## Configuration

### Required Supabase Settings

Your Supabase project must be configured with:

```javascript
{
  "site_url": "https://getreceipts.org",
  "redirect_urls": [
    "http://localhost:8080/auth/callback",
    "http://127.0.0.1:8080/auth/callback"
  ]
}
```

### Required Tables

The following tables must exist in Supabase with RLS policies:

- `auth.users` (automatically created)
- `auth.sessions` (automatically created)
- `auth.refresh_tokens` (automatically created)
- `auth.identities` (for OAuth provider linking)
- `public.profiles` (optional, for user profile data)

## Troubleshooting

### Common Issues

#### "Auth Unavailable"
- **Cause**: Supabase client not properly configured
- **Solution**: Check Supabase URL and key in settings

#### "OAuth authentication failed or timed out"
- **Cause**: User didn't complete OAuth flow within 5 minutes
- **Solution**: Try again, complete authentication more quickly

#### "Failed to establish session"
- **Cause**: Invalid tokens or Supabase configuration issue
- **Solution**: Check Supabase redirect URL configuration

#### "Port 8080 already in use"
- **Cause**: Another process is using port 8080
- **Solution**: Stop other processes or restart Knowledge_Chipper

### Testing

Run the test script to verify OAuth functionality:

```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper
python scripts/test_oauth_flow.py
```

### Debugging

Enable debug logging to see detailed OAuth flow information:

```python
import logging
logging.getLogger("knowledge_system.services.oauth_callback_server").setLevel(logging.DEBUG)
logging.getLogger("knowledge_system.services.supabase_auth").setLevel(logging.DEBUG)
```

## Security Considerations

### Production Deployment

- ✅ **HTTPS Only**: GetReceipts uses HTTPS for OAuth
- ✅ **Token Expiry**: JWT tokens have built-in expiration
- ✅ **Secure Storage**: Tokens stored in Supabase client memory only
- ✅ **RLS Policies**: Database-level access control
- ⚠️ **Local Callback**: Uses HTTP for localhost callback (acceptable)

### Best Practices

1. **Always use OAuth** for production authentication
2. **Check authentication status** before sensitive operations
3. **Handle token refresh** automatically via Supabase client
4. **Log out properly** to clear tokens
5. **Monitor authentication logs** for security issues

## Development

### Adding OAuth Providers

To add additional OAuth providers:

1. **Update OAuth URL** in `SupabaseAuthService.sign_up_with_oauth()`
2. **Configure provider** in Supabase dashboard
3. **Update redirect URLs** as needed
4. **Test authentication flow**

### Customizing UI

The OAuth UI can be customized by modifying:

- Button styles in `_create_auth_section()`
- Progress dialog text in `_sign_in_with_oauth()`
- Success/error messages throughout the flow

### Error Handling

All OAuth methods return `(success: bool, message: str)` tuples for consistent error handling.

## Support

For OAuth integration issues:

1. **Check logs** in `logs/knowledge_system.log`
2. **Run test script** to verify functionality
3. **Verify Supabase configuration** in dashboard
4. **Check GetReceipts OAuth settings** if available
5. **Use legacy authentication** as fallback if needed

## Future Enhancements

Planned improvements to the OAuth integration:

- [ ] **Multiple OAuth Providers**: Support for Google, GitHub, etc.
- [ ] **Token Refresh UI**: Visual indicators for token status
- [ ] **Offline Mode**: Graceful handling when OAuth unavailable
- [ ] **SSO Integration**: Enterprise single sign-on support
- [ ] **Mobile OAuth**: Support for mobile app authentication
