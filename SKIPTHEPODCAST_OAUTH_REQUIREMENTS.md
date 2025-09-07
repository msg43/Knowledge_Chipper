# SkipThePodcast.com OAuth Implementation Requirements

## Overview

Knowledge_Chipper needs OAuth authentication through SkipThePodcast.com using **Supabase native OAuth and tokens**. This document provides the exact implementation requirements for SkipThePodcast.com to integrate with Knowledge_Chipper's existing OAuth flow.

## How Knowledge_Chipper OAuth Works

1. **User clicks "Sign In"** in Knowledge_Chipper
2. **Browser opens** to `https://skipthepodcast.com/auth/signin?redirect_to=knowledge_chipper&return_url=http://localhost:8080/auth/callback`
3. **User authenticates** on SkipThePodcast.com (trusted domain)
4. **SkipThePodcast.com uses Supabase** to authenticate user and get session tokens
5. **SkipThePodcast.com redirects** back with Supabase tokens:
   ```
   http://localhost:8080/auth/callback?access_token=SUPABASE_TOKEN&refresh_token=SUPABASE_REFRESH&user_id=USER_ID
   ```
6. **Knowledge_Chipper receives tokens** and calls `supabase.auth.setSession(access_token, refresh_token)`
7. **User is authenticated** and can upload data to shared Supabase database

---

## Required Implementation

### 1. Supabase Client Setup

SkipThePodcast.com must use **the exact same Supabase project** as Knowledge_Chipper:

```javascript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  'https://sdkxuiqcwlmbpjvjdpkj.supabase.co',
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNka3h1aXFjd2xtYnBqdmpkcGtqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU4MTU3MzQsImV4cCI6MjA3MTM5MTczNH0.VoP6yX3GwyVjylgioTGchQYwPQ_K2xQFdHP5ani0vts'
)
```

### 2. OAuth Endpoints

#### Primary OAuth Endpoint

```javascript
// GET /auth/signin
app.get('/auth/signin', (req, res) => {
  const { redirect_to, return_url } = req.query;
  
  // CRITICAL: Validate parameters exactly
  if (redirect_to !== 'knowledge_chipper') {
    return res.status(400).json({ 
      error: 'invalid_request', 
      message: 'Invalid redirect_to parameter' 
    });
  }
  
  if (!return_url || !return_url.startsWith('http://localhost:8080/auth/callback')) {
    return res.status(400).json({ 
      error: 'invalid_request', 
      message: 'Invalid return_url parameter' 
    });
  }
  
  // Store OAuth state in session for security
  req.session.oauth_return_url = return_url;
  req.session.oauth_app = redirect_to;
  
  // Show sign-in/register page
  res.render('oauth-signin', { 
    return_url: return_url,
    app_name: 'Knowledge_Chipper',
    signin_url: '/auth/signin-form',
    register_url: '/auth/register-form'
  });
});
```

#### Sign-In Handler

```javascript
// POST /auth/signin-form
app.post('/auth/signin-form', async (req, res) => {
  const { email, password } = req.body;
  const return_url = req.session.oauth_return_url;
  
  if (!return_url) {
    return res.status(400).json({ error: 'Invalid session state' });
  }
  
  try {
    // Authenticate with Supabase
    const { data, error } = await supabase.auth.signInWithPassword({
      email: email,
      password: password
    });
    
    if (error) {
      return res.render('oauth-signin', { 
        error: 'Invalid credentials. Please try again.',
        return_url: return_url,
        app_name: 'Knowledge_Chipper'
      });
    }
    
    if (!data.session || !data.user) {
      return res.render('oauth-signin', { 
        error: 'Authentication failed. Please try again.',
        return_url: return_url,
        app_name: 'Knowledge_Chipper'
      });
    }
    
    // Clear OAuth session data
    delete req.session.oauth_return_url;
    delete req.session.oauth_app;
    
    // Redirect with Supabase tokens
    const callback_url = `${return_url}?access_token=${data.session.access_token}&refresh_token=${data.session.refresh_token}&user_id=${data.user.id}`;
    
    res.redirect(callback_url);
    
  } catch (error) {
    console.error('OAuth sign-in error:', error);
    const error_url = `${return_url}?error=server_error&error_description=Authentication failed`;
    res.redirect(error_url);
  }
});
```

#### Registration Handler

```javascript
// POST /auth/register-form
app.post('/auth/register-form', async (req, res) => {
  const { email, password, confirm_password, name } = req.body;
  const return_url = req.session.oauth_return_url;
  
  if (!return_url) {
    return res.status(400).json({ error: 'Invalid session state' });
  }
  
  // Validate input
  if (password !== confirm_password) {
    return res.render('oauth-signin', {
      error: 'Passwords do not match',
      return_url: return_url,
      app_name: 'Knowledge_Chipper'
    });
  }
  
  if (password.length < 6) {
    return res.render('oauth-signin', {
      error: 'Password must be at least 6 characters',
      return_url: return_url,
      app_name: 'Knowledge_Chipper'
    });
  }
  
  try {
    // Register with Supabase
    const { data, error } = await supabase.auth.signUp({
      email: email,
      password: password,
      options: {
        data: {
          display_name: name,
          name: name,
          full_name: name
        }
      }
    });
    
    if (error) {
      return res.render('oauth-signin', {
        error: error.message,
        return_url: return_url,
        app_name: 'Knowledge_Chipper'
      });
    }
    
    // Clear OAuth session data
    delete req.session.oauth_return_url;
    delete req.session.oauth_app;
    
    if (data.session && data.user) {
      // User is immediately signed in (email confirmation disabled)
      const callback_url = `${return_url}?access_token=${data.session.access_token}&refresh_token=${data.session.refresh_token}&user_id=${data.user.id}`;
      res.redirect(callback_url);
    } else if (data.user && !data.session) {
      // Email confirmation required
      res.render('oauth-confirmation', { 
        message: 'Please check your email to confirm your account, then try signing in again.',
        return_url: return_url,
        app_name: 'Knowledge_Chipper'
      });
    } else {
      throw new Error('Registration failed');
    }
    
  } catch (error) {
    console.error('OAuth registration error:', error);
    const error_url = `${return_url}?error=server_error&error_description=Registration failed`;
    res.redirect(error_url);
  }
});
```

### 3. Required HTML Templates

#### OAuth Sign-In Page (`views/oauth-signin.ejs`)

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign In - SkipThePodcast.com</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            max-width: 400px; 
            margin: 50px auto; 
            padding: 20px;
            background-color: #f5f5f5;
        }
        .auth-container {
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .app-info {
            text-align: center;
            margin-bottom: 30px;
            padding: 15px;
            background-color: #e3f2fd;
            border-radius: 4px;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
        input[type="email"], input[type="password"], input[type="text"] {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }
        .btn {
            width: 100%;
            padding: 12px;
            background-color: #2196F3;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            margin-bottom: 10px;
        }
        .btn:hover {
            background-color: #1976D2;
        }
        .error {
            color: #d32f2f;
            margin-bottom: 15px;
            padding: 10px;
            background-color: #ffebee;
            border-radius: 4px;
        }
        .tabs {
            display: flex;
            margin-bottom: 20px;
        }
        .tab {
            flex: 1;
            padding: 10px;
            text-align: center;
            background-color: #f0f0f0;
            cursor: pointer;
            border: 1px solid #ddd;
        }
        .tab.active {
            background-color: #2196F3;
            color: white;
        }
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
        }
    </style>
</head>
<body>
    <div class="auth-container">
        <div class="app-info">
            <h2>🔐 Authorize Knowledge_Chipper</h2>
            <p><strong>Knowledge_Chipper</strong> wants to access your SkipThePodcast.com account</p>
            <p><small>This will allow you to upload and manage your claims data securely.</small></p>
        </div>

        <% if (typeof error !== 'undefined' && error) { %>
            <div class="error"><%= error %></div>
        <% } %>

        <div class="tabs">
            <div class="tab active" onclick="showTab('signin')">Sign In</div>
            <div class="tab" onclick="showTab('register')">Register</div>
        </div>

        <!-- Sign In Form -->
        <div id="signin-tab" class="tab-content active">
            <form action="/auth/signin-form" method="POST">
                <div class="form-group">
                    <label for="email">Email</label>
                    <input type="email" id="email" name="email" required>
                </div>
                <div class="form-group">
                    <label for="password">Password</label>
                    <input type="password" id="password" name="password" required>
                </div>
                <button type="submit" class="btn">Sign In & Authorize</button>
            </form>
        </div>

        <!-- Register Form -->
        <div id="register-tab" class="tab-content">
            <form action="/auth/register-form" method="POST">
                <div class="form-group">
                    <label for="reg-name">Name</label>
                    <input type="text" id="reg-name" name="name" required>
                </div>
                <div class="form-group">
                    <label for="reg-email">Email</label>
                    <input type="email" id="reg-email" name="email" required>
                </div>
                <div class="form-group">
                    <label for="reg-password">Password</label>
                    <input type="password" id="reg-password" name="password" required minlength="6">
                </div>
                <div class="form-group">
                    <label for="reg-confirm">Confirm Password</label>
                    <input type="password" id="reg-confirm" name="confirm_password" required>
                </div>
                <button type="submit" class="btn">Create Account & Authorize</button>
            </form>
        </div>

        <div style="text-align: center; margin-top: 20px;">
            <a href="/" style="color: #666;">Cancel</a>
        </div>
    </div>

    <script>
        function showTab(tabName) {
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected tab
            document.getElementById(tabName + '-tab').classList.add('active');
            event.target.classList.add('active');
        }
    </script>
</body>
</html>
```

#### Email Confirmation Page (`views/oauth-confirmation.ejs`)

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Email Confirmation - SkipThePodcast.com</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            max-width: 400px; 
            margin: 50px auto; 
            padding: 20px;
            background-color: #f5f5f5;
        }
        .auth-container {
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            text-align: center;
        }
        .message {
            color: #2196F3;
            margin-bottom: 20px;
            padding: 15px;
            background-color: #e3f2fd;
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <div class="auth-container">
        <h2>📧 Check Your Email</h2>
        <div class="message">
            <%= message %>
        </div>
        <p>After confirming your email, you can return to Knowledge_Chipper and sign in again.</p>
        <div style="margin-top: 20px;">
            <a href="/" style="color: #666;">Return to SkipThePodcast.com</a>
        </div>
    </div>
</body>
</html>
```

### 4. Session Configuration

```javascript
// Required session setup
const session = require('express-session');

app.use(session({
  secret: process.env.SESSION_SECRET || 'your-secure-session-secret',
  resave: false,
  saveUninitialized: false,
  cookie: {
    secure: process.env.NODE_ENV === 'production', // HTTPS in production
    httpOnly: true,
    maxAge: 24 * 60 * 60 * 1000 // 24 hours
  }
}));
```

### 5. Required Callback Format

Knowledge_Chipper expects these exact URL formats:

**Success:**
```
http://localhost:8080/auth/callback?access_token=SUPABASE_ACCESS_TOKEN&refresh_token=SUPABASE_REFRESH_TOKEN&user_id=SUPABASE_USER_ID
```

**Error:**
```
http://localhost:8080/auth/callback?error=ERROR_CODE&error_description=ERROR_MESSAGE
```

### 6. Security Requirements

- **Validate `redirect_to`** must equal `"knowledge_chipper"` exactly
- **Validate `return_url`** must start with `"http://localhost:8080/auth/callback"`
- **Use HTTPS** for production deployment
- **Secure session management** with proper secrets
- **Rate limiting** on authentication endpoints
- **Input validation** on all form fields

### 7. Supabase Project Configuration

Ensure your Supabase project settings include:

```javascript
// In Supabase Dashboard > Authentication > URL Configuration
{
  "site_url": "https://skipthepodcast.com",
  "redirect_urls": [
    "http://localhost:8080/auth/callback",
    "http://127.0.0.1:8080/auth/callback"
  ]
}
```

### 8. Environment Variables

```bash
# Required environment variables
SESSION_SECRET=your-super-secure-session-secret-here
NODE_ENV=production  # for production deployment
SUPABASE_URL=https://sdkxuiqcwlmbpjvjdpkj.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNka3h1aXFjd2xtYnBqdmpkcGtqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU4MTU3MzQsImV4cCI6MjA3MTM5MTczNH0.VoP6yX3GwyVjylgioTGchQYwPQ_K2xQFdHP5ani0vts
```

---

## Implementation Checklist

- [ ] **Install Supabase client** with exact project credentials above
- [ ] **Create `GET /auth/signin` endpoint** that validates parameters and shows auth form
- [ ] **Create `POST /auth/signin-form` handler** using `supabase.auth.signInWithPassword()`
- [ ] **Create `POST /auth/register-form` handler** using `supabase.auth.signUp()`
- [ ] **Create HTML templates** for sign-in and confirmation pages
- [ ] **Add session management** with secure configuration
- [ ] **Add input validation** and error handling
- [ ] **Add security measures** (rate limiting, HTTPS, etc.)
- [ ] **Configure Supabase project** with correct redirect URLs
- [ ] **Test OAuth flow** with Knowledge_Chipper

## Testing

Once implemented, test with:

```bash
# Should return HTML page (not 404)
curl "https://skipthepodcast.com/auth/signin?redirect_to=knowledge_chipper&return_url=http://localhost:8080/auth/callback"

# Test from Knowledge_Chipper
# 1. Open Knowledge_Chipper
# 2. Go to Cloud Uploads tab
# 3. Click "Sign In with SkipThePodcast"
# 4. Complete authentication flow
# 5. Verify tokens are received and session established
```

## Key Points

1. **Use Supabase native authentication** - not custom JWT tokens
2. **Return actual Supabase session tokens** that Knowledge_Chipper can use directly
3. **Validate all OAuth parameters** for security
4. **Handle both sign-in and registration** flows
5. **Use the exact same Supabase project** as Knowledge_Chipper
6. **Follow the exact callback URL format** that Knowledge_Chipper expects

This implementation makes SkipThePodcast.com a **Supabase OAuth proxy** - it provides the UI/UX for authentication but uses Supabase for the actual token generation and session management.
