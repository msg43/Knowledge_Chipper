# Bright Data Setup Guide

**Complete setup guide for Bright Data integration with Knowledge System**

## Overview

Bright Data provides reliable residential proxies and API scrapers for YouTube processing. This integration offers several advantages over traditional proxy services:

✅ **Pay-per-request model** - More cost-effective than monthly subscriptions  
✅ **Automatic IP rotation** - Built-in residential proxy management  
✅ **Direct JSON responses** - Cleaner data pipeline with YouTube API Scrapers  
✅ **Session management** - Sticky IP sessions for optimal performance  
✅ **Comprehensive analytics** - Built-in cost tracking and usage monitoring  

## Prerequisites

1. **Bright Data Account** - Sign up at [brightdata.com](https://brightdata.com/)
2. **Knowledge System** - Version with Bright Data integration
3. **API Key** - Obtain from your Bright Data dashboard

## Step 1: Bright Data Account Setup

### 1.1 Create Account
1. Visit [brightdata.com](https://brightdata.com/)
2. Sign up for a new account
3. Complete account verification
4. Add payment method for pay-per-use billing

### 1.2 Create Residential Proxy Zone
1. In Bright Data dashboard: **Products → Residential Proxies**
2. Click **"Add Zone"**
3. Configure zone settings:
   - **Zone Name**: `knowledge-system-residential`
   - **IP Type**: Residential
   - **Location**: Your preferred country/city
   - **Rotation**: Session (sticky sessions)
   - **Concurrent Sessions**: 10-50 (based on usage)

4. Note down:
   - **Customer ID** (format: `c_xxxxxxx`)
   - **Zone Name** (what you created above)
   - **Zone Password** (generated automatically)

### 1.3 Get API Credentials
1. Go to **"API"** section in dashboard
2. Create new API key with permissions:
   - Scraping API access
   - Zone management
   - Usage statistics
3. Copy the API key (format: `2e53ca9f...`)

## Step 2: Knowledge System Configuration

### 2.1 Environment Variables (Recommended)
Set these environment variables for secure credential management:

```bash
# Add to your shell profile (.bashrc, .zshrc, etc.)
export BD_CUST="c_xxxxxxx"           # Your customer ID
export BD_ZONE="knowledge-system-residential"  # Your zone name  
export BD_PASS="your_zone_password"  # Zone password
export BRIGHT_DATA_API_KEY="2e53ca9f..."  # Your API key
```

### 2.2 GUI Configuration (Alternative)
1. Launch Knowledge System GUI
2. Go to **"API Keys"** tab
3. Fill in Bright Data credentials:
   - **Bright Data API Key**: Your API key
   - **Customer ID**: From Bright Data dashboard
   - **Zone ID**: Your zone name
   - **Password**: Zone password
4. Click **"Save API Keys"**

### 2.3 Configuration File (Manual)
Edit `config/credentials.yaml`:

```yaml
api_keys:
  bright_data_api_key: "2e53ca9f..."
  bright_data_customer_id: "c_xxxxxxx"
  bright_data_zone_id: "knowledge-system-residential"
  bright_data_password: "your_zone_password"
```

## Step 3: Verify Setup

### 3.1 Test Connection
```bash
# Test Bright Data integration
knowledge-system database stats

# Process a test video
knowledge-system process "https://youtube.com/watch?v=dQw4w9WgXcQ" \
  --transcribe --summarize
```

### 3.2 Check Costs
```bash
# Monitor usage and costs
knowledge-system database budget --budget 50.00

# View session statistics
knowledge-system database jobs --limit 5
```

## Step 4: Cost Management

### 4.1 Budget Monitoring
Set up budget alerts to control costs:

```bash
# Check monthly budget status
knowledge-system database budget --budget 100.00

# Get detailed cost breakdown
knowledge-system database stats --days 30
```

### 4.2 Cost Optimization Features

**Automatic Deduplication:**
- Prevents reprocessing of duplicate videos
- Saves 30-50% on processing costs
- Enabled by default

**Session Management:**
- One sticky IP per video download
- Optimal connection pooling (2-4 connections per file)
- Automatic session cleanup

**Usage Analytics:**
- Real-time cost tracking per video
- Session-level cost attribution
- Monthly usage reports

## Step 5: Advanced Configuration

### 5.1 Session Optimization
Configure optimal settings in your Bright Data dashboard:

```
Concurrent Sessions: 20-50 (based on usage volume)
Session Duration: 10 minutes (default)
IP Rotation: Per session (sticky within session)
Retry Logic: 3 retries with exponential backoff
```

### 5.2 Performance Tuning
For high-volume processing:

```yaml
# config/settings.yaml
youtube_processing:
  concurrent_downloads: 4
  session_timeout: 300
  retry_attempts: 3
  
bright_data:
  max_sessions: 50
  session_ttl: 600  # 10 minutes
  cost_per_gb: 0.50  # Update based on your pricing
```

## Step 6: Monitoring & Maintenance

### 6.1 Regular Monitoring
```bash
# Daily cost check
knowledge-system database stats --days 1

# Weekly budget review  
knowledge-system database budget --budget 100.00

# Monthly cleanup
knowledge-system database cleanup --days 30
```

### 6.2 Cost Alerts
The system provides automatic alerts:
- **Yellow**: 50% of budget used
- **Red**: 80% of budget used or projected overage

### 6.3 Database Maintenance
```bash
# Clean up old jobs and sessions
knowledge-system database cleanup --days 30

# Vacuum database to reclaim space
# (Runs automatically with cleanup)
```

## Troubleshooting

### Common Issues

**"Bright Data credentials incomplete"**
- Check all credentials are set (Customer ID, Zone, Password, API Key)
- Verify environment variables or GUI configuration
- Test connection in Bright Data dashboard

**"Failed to create session"**  
- Check zone status in Bright Data dashboard
- Verify concurrent session limits
- Check account billing status

**"High costs detected"**
- Enable deduplication (enabled by default)
- Review session usage patterns
- Check for failed retries causing extra requests
- Monitor budget alerts

**"Proxy connection timeout"**
- Check zone configuration
- Verify IP restrictions in dashboard
- Test with different geographic locations

### Support Resources

1. **Bright Data Documentation**: [docs.brightdata.com](https://docs.brightdata.com/)
2. **Knowledge System Issues**: Check project repository
3. **Cost Optimization**: Use built-in analytics and recommendations

## Migration from WebShare

If migrating from WebShare, the system provides automatic fallback:

1. **Keep existing WebShare credentials** for compatibility
2. **Add Bright Data credentials** - system will prefer Bright Data
3. **Monitor costs** during transition period
4. **Remove WebShare credentials** once migration is complete

The system automatically detects available credentials and uses Bright Data when configured, falling back to WebShare if needed.

## Cost Comparison

| Service | Model | Typical Cost | Benefits |
|---------|-------|--------------|----------|
| WebShare | Monthly subscription | $30-100/month | Flat rate, unlimited |
| Bright Data | Pay-per-use | $0.001-0.01 per request | Pay only for usage, better reliability |

**Example**: Processing 100 videos/month
- WebShare: $50/month (fixed)
- Bright Data: $5-15/month (variable, typically less)

## Security Notes

🔒 **Credential Security:**
- Use environment variables for production
- Never commit credentials to version control
- Rotate API keys periodically
- Monitor usage for unusual activity

🛡️ **Network Security:**
- Bright Data uses HTTPS/SSL encryption
- Residential IPs reduce detection risk
- Session isolation prevents cross-contamination

---

**Need Help?** Check the Knowledge System documentation or create an issue in the project repository.
