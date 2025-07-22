# Webshare Proxy Setup for YouTube Transcript Extraction

This system uses Webshare residential proxies to bypass YouTube's bot detection when extracting transcripts. Webshare automatically handles IP rotation behind the scenes - no complex setup needed!

## 1. Get Webshare Account

1. Go to [Webshare.io](https://www.webshare.io/)
2. Sign up for an account
3. Choose a residential proxy plan with rotating endpoints

## 2. Get Your Credentials

From your Webshare dashboard, you'll need:

- **Username**: Your proxy username (should end with `-rotate` for automatic rotation)
- **Password**: Your proxy password 

That's it! No API tokens or complex configuration needed.

## 3. Set Environment Variables

Add these environment variables to your system:

```bash
# Required credentials (Webshare handles rotation automatically)
export WEBSHARE_USERNAME="your-username-rotate"
export WEBSHARE_PASSWORD="your-password-here"
```

### On macOS/Linux:
Add to your `~/.bashrc`, `~/.zshrc`, or `~/.profile`:

```bash
export WEBSHARE_USERNAME="your-username-rotate"
export WEBSHARE_PASSWORD="your-password-here"
```

### On Windows:
Set via Command Prompt:
```cmd
set WEBSHARE_USERNAME=your-username-rotate
set WEBSHARE_PASSWORD=your-password-here
```

Or via PowerShell:
```powershell
$env:WEBSHARE_USERNAME="your-username-rotate"
$env:WEBSHARE_PASSWORD="your-password-here"
```

## 4. How It Works

The system will:

1. **Load your proxy credentials** from environment variables
2. **Connect to Webshare's rotating endpoint** (`p.webshare.io:80`)
3. **Webshare automatically rotates IP addresses** for each request
4. **Use residential IP addresses** to avoid bot detection
5. **Automatically retry** with random delays if requests fail

## 5. Troubleshooting

### "Webshare credentials not found" error:
- Make sure environment variables are set correctly
- Restart your terminal/application after setting variables
- Check that variable names match exactly (case-sensitive)

### "All attempts failed" error:
- Your proxy quota might be exhausted
- Check your Webshare dashboard for usage limits
- Make sure your username ends with `-rotate`

### Still getting blocked:
- Make sure you're using residential proxies (not datacenter)
- Check if your Webshare account is active
- Verify you have sufficient proxy bandwidth remaining

## 6. Cost Considerations

- Residential proxies are more expensive than datacenter proxies
- Each transcript request uses bandwidth
- Monitor your usage in the Webshare dashboard
- Consider batching requests to optimize costs

## 7. Technical Details

The system connects directly to Webshare's rotating proxy endpoint:
- **Host**: `p.webshare.io`  
- **Port**: `80`
- **Authentication**: Your username and password
- **IP Rotation**: Automatic (handled by Webshare)
- **Implementation**: Simple inline code in the processor (no external dependencies)

Each request may come from a different residential IP address, making it nearly impossible for YouTube to detect automated access. 