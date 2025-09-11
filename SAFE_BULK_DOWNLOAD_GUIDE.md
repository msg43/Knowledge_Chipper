# Safe Bulk Download Guide

## ⚠️ WARNING: Personal Cookie Risks

Using your personal YouTube cookies for bulk downloads (like 5000 videos) can result in:
- **Account suspension or ban**
- **Loss of access to your Google/YouTube account**
- **Violation of YouTube's Terms of Service**
- **Legal liability**

## Safer Alternatives for Large-Scale Operations

### 1. Use Transcript API (No Audio Download)
The system supports fetching transcripts without downloading audio:
- Uses `youtube-transcript-api` 
- Much lower risk of detection
- Faster and uses less bandwidth
- Still requires some form of authentication

### 2. Distributed Cookie Approach
Instead of using one personal account:

#### Create Multiple Accounts
- Set up 10-20 YouTube accounts specifically for this
- Use different email addresses
- Access from different IPs when creating
- Let accounts "age" for a few weeks before use

#### Rotate Cookie Files
```bash
# Create directory for multiple cookie files
mkdir -p ~/.config/knowledge_system/cookie_rotation/

# Save cookies as:
~/.config/knowledge_system/cookie_rotation/cookies_001.txt
~/.config/knowledge_system/cookie_rotation/cookies_002.txt
# ... etc
```

#### Implement Rotation Logic
- Use one account per 100-200 downloads
- Switch accounts after hitting limits
- Add significant delays between account switches

### 3. Rate Limiting Strategy

Add these safeguards to your workflow:

```python
# Recommended limits
MAX_DOWNLOADS_PER_ACCOUNT_PER_DAY = 100
DELAY_BETWEEN_DOWNLOADS = 30  # seconds
DELAY_BETWEEN_BATCHES = 300  # 5 minutes
ACCOUNTS_TO_ROTATE = 10
```

### 4. YouTube Data API (Most Legal)

For legitimate research/business use:
- Apply for YouTube Data API access
- Use official API quotas
- Completely legal and supported
- Limited to 10,000 units per day

### 5. Proxy-Only Approach (Less Reliable)

Without cookies, rely purely on proxy rotation:
- Will have higher failure rate
- More "bot detection" errors
- But zero risk to personal accounts
- Use with retry logic

## Recommended Approach for 5000 URLs

1. **Split the job**: 
   - 500 URLs per day over 10 days
   - Or 100 URLs per day over 50 days

2. **Use multiple approaches**:
   - Try transcript API first (no audio)
   - Fall back to audio download only if needed
   - Use proxy rotation without cookies

3. **Monitor and adapt**:
   - Log all errors
   - If seeing increased failures, slow down
   - Have backup plans

## Implementation Example

```bash
# Day 1: URLs 1-500 with conservative settings
python -m knowledge_system youtube \
  --urls urls_batch_1.txt \
  --delay 30 \
  --max-concurrent 2

# Day 2: URLs 501-1000 (after checking no issues)
python -m knowledge_system youtube \
  --urls urls_batch_2.txt \
  --delay 30 \
  --max-concurrent 2
```

## Emergency Procedures

If your account gets flagged:
1. **Stop immediately**
2. Don't try to "push through" blocks
3. Wait 24-48 hours before trying again
4. Consider the account "burned" for bulk operations

## Ethical Considerations

- Respect content creators' rights
- Consider if you really need all 5000 videos
- Check if the content is available through legal APIs
- Consider reaching out to content owners directly

## The Bottom Line

**For 5000 downloads**: Don't use your personal account cookies. The risk of losing your Google account isn't worth it. Use distributed approaches, official APIs, or accept a higher failure rate with proxy-only methods.
