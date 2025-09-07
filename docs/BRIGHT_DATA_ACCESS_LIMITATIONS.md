# Bright Data Access Limitations

## Overview

This document outlines the access limitations that apply to Bright Data residential proxies when using **Immediate Access** mode. These limitations can be removed by completing **Enhanced KYC (Know Your Customer)** verification to unlock **Full Access** mode.

## Current Access Limitations (Immediate Access Mode)

### 1. Domain Restrictions

#### Robots.txt Compliance
- **Limitation**: Domains that have restrictive `robots.txt` rules may be blocked
- **Impact**: Cannot access websites that explicitly disallow automated access
- **Resolution**: Enhanced KYC enables bypass of robots.txt restrictions

#### Bright Data Compliance Policy
- **Limitation**: Certain domains are restricted by Bright Data's internal compliance policy
- **Impact**: Access to specific websites may be denied even if technically accessible
- **Resolution**: Enhanced KYC provides access to previously restricted domains

### 2. HTTP Method Restrictions

#### Allowed Methods
- ✅ **GET**: Full support for data retrieval
- ✅ **HEAD**: Supported for metadata requests

#### Restricted Methods
- ❌ **POST**: Not permitted in Immediate Access mode
- ❌ **PUT**: Not permitted in Immediate Access mode  
- ❌ **DELETE**: Not permitted in Immediate Access mode
- ❌ **PATCH**: Not permitted in Immediate Access mode

### 3. Rate Limiting and Throttling

#### Automatic Throttling
- **Trigger**: Request volume exceeding acceptable thresholds
- **Response**: HTTP Status Code `502`
- **Error Message**: `sr_rate_limit`
- **Impact**: Temporary blocking when request rate is too high
- **Mitigation**: Implement request spacing and retry logic

### 4. Error Responses

#### Common Error Codes

**402 Residential Failed (bad_endpoint)**
- **Cause**: Attempting to access restricted domains or use forbidden HTTP methods
- **Solution**: Apply for Enhanced KYC to enable Full Access mode
- **Alternative**: Modify request to use allowed methods/domains

**502 Rate Limited (sr_rate_limit)**
- **Cause**: Request volume exceeding acceptable thresholds
- **Solution**: Implement rate limiting in application
- **Retry**: Wait before retrying requests

## Upgrading to Full Access Mode

### Enhanced KYC Process
To remove these limitations, complete Bright Data's Enhanced KYC verification:

1. **Access Bright Data Dashboard**
   - Log into your Bright Data account
   - Navigate to Account Settings

2. **Submit Enhanced KYC Documentation**
   - Business verification documents
   - Use case documentation
   - Compliance attestation

3. **Approval Process**
   - Review typically takes 1-3 business days
   - May require additional documentation
   - Direct communication with Bright Data compliance team

### Benefits of Full Access Mode
- ✅ No domain restrictions
- ✅ All HTTP methods supported (POST, PUT, DELETE, PATCH)
- ✅ Higher rate limits
- ✅ Access to restricted websites
- ✅ Priority support

## Impact on Knowledge Chipper

### Current Functionality (Immediate Access)
The Knowledge Chipper system is designed to work within these limitations:

- **YouTube Processing**: Uses GET requests only ✅
- **Metadata Extraction**: Compatible with current restrictions ✅
- **Transcript Download**: Works with allowed HTTP methods ✅
- **Rate Limiting**: Built-in throttling and retry logic ✅

### Potential Issues
- **Custom Domains**: Some specialized YouTube-like platforms may be restricted
- **High Volume Processing**: May trigger rate limiting on large batches
- **Advanced Features**: Future features requiring POST/PUT may need Full Access

## Recommendations

### Immediate Actions
1. **Monitor Error Rates**: Watch for 402 and 502 errors in processing logs
2. **Implement Retry Logic**: Handle rate limiting gracefully
3. **Batch Processing**: Space out requests to avoid throttling

### Long-term Strategy
1. **Enhanced KYC**: Consider upgrading for unrestricted access
2. **Fallback Methods**: Implement alternative processing for restricted content
3. **Cost Monitoring**: Track usage to optimize request patterns

## Troubleshooting

### If You Encounter Restrictions
1. **Check Error Codes**: Identify whether it's domain or rate limiting
2. **Review Request Pattern**: Ensure using only GET/HEAD methods
3. **Contact Support**: Bright Data support can clarify specific restrictions
4. **Consider Enhanced KYC**: For persistent issues with domain access

### Monitoring Commands
```bash
# Check recent processing errors
knowledge-system database jobs --limit 10

# Monitor error patterns
knowledge-system database stats --days 7

# Review cost and usage patterns  
knowledge-system database budget --budget 100.00
```

## Enhanced KYC Process Details

### KYC Timeline
Based on Bright Data's official documentation:
- **Company KYC**: Usually takes up to 5 minutes to submit
- **Freelancer KYC**: Takes up to 10 minutes to submit, requires video call
- **Review Process**: Allow 2 business days for compliance review
- **Status Tracking**: Check status in Control Panel under Account > Profile

### Required Documentation
**For Companies:**
- Company registration certificate/certificate of incorporation
- Business use case description
- Company email domain verification

**For Freelancers:**
- Valid government-issued ID (passport, driver's license)
- Personal use case description
- Mandatory video call for identity verification

### KYC Application Process
1. **Start KYC**: Available in Bright Data Control Panel (requires real funds, not available in trial mode)
2. **Submit Documentation**: Provide required business/personal information
3. **Video Call** (freelancers only): Quick identity verification and use case review
4. **Compliance Review**: 2 business day review by Bright Data's team
5. **Notification**: Email confirmation of approval/decline

### Important Notes
- KYC is **mandatory** for Full Access to residential network
- **Business use cases only** - personal projects are not approved
- One-time process, but may require future clarifications
- Can use other Bright Data services during KYC review

## Support Resources

- **Official KYC Documentation**: [Bright Data Network Access Policy](https://docs.brightdata.com/proxy-networks/residential/network-access#what-is-the-process-for-kyc-verification)
- **General Documentation**: [docs.brightdata.com](https://docs.brightdata.com/)
- **Compliance Support**: Available through Bright Data dashboard
- **KYC Application**: Start in Control Panel under Account settings
- **Knowledge Chipper Issues**: Check project repository for updates

---

**Last Updated**: September 2025  
**Version**: 1.1  
**Status**: Active for Immediate Access accounts  
**Source**: [Bright Data Official Documentation](https://docs.brightdata.com/proxy-networks/residential/network-access)
