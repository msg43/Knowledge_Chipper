# System Limits Configuration

**Version:** 1.0.0  
**Last Updated:** December 29, 2025  
**Status:** ✅ Active

## Overview

This document defines all numerical limits and caps throughout the Knowledge_Chipper and GetReceipts system. All limits are set generously high to allow maximum flexibility during initial rollout.

---

## 📊 Content Ingestion Limits

### RSS/Podcast Feeds
- **Default**: `9999` episodes per feed
- **Maximum**: `99999` episodes per feed
- **Rationale**: Effectively unlimited to support large podcast libraries
- **Files**:
  - `daemon/models/schemas.py` - Field validation
  - `daemon/services/rss_service.py` - Service method
  - `daemon/services/processing_service.py` - Batch processing
  - `daemon/api/routes.py` - API endpoint
  - `src/components/processing-options.tsx` - Frontend UI
  - `src/app/contribute/help/page.tsx` - Documentation

### Job History
- **Limit**: `500` jobs stored in memory
- **Rationale**: Memory management for long-running daemon
- **File**: `daemon/services/processing_service.py`
- **Recommendation**: Consider database persistence for larger history

### Monitor Events
- **Limit**: `100` events maximum
- **Rationale**: Folder watch activity logging
- **File**: `daemon/services/monitor_service.py`
- **Recommendation**: Consider rotating log file for long-term history

---

## ☁️ Upload & API Limits (GetReceipts)

### Rate Limiting
- **Limit**: `99999` uploads per hour per authentication source
- **Window**: Rolling 60-minute window
- **Rationale**: Effectively unlimited for initial rollout, can be tightened later
- **Files**:
  - `src/lib/auth/upload-auth.ts` - Default parameter
  - `src/app/api/knowledge-chipper/upload/route.ts` - Enforcement
  - `UPLOAD_SECURITY.md` - Documentation

**Response**: 429 Too Many Requests with reset timestamp when exceeded

### Records Per Upload
- **Limit**: `99999` records per single upload
- **Rationale**: Allows large batch uploads while preventing accidental massive uploads
- **File**: `src/app/api/knowledge-chipper/upload/route.ts`
- **Applies to**: Total of all records across all tables (media_sources, claims, jargon, people, concepts, etc.)

**Response**: 400 Bad Request when exceeded

### Claim Text Length
- **Limit**: `10000` characters maximum
- **Rationale**: Data quality - prevents excessively long claim text
- **File**: `src/app/api/knowledge-chipper/upload/route.ts`
- **Recommendation**: Keep this limit for data quality

**Response**: 400 Bad Request with validation error

---

## 🔍 Query & Search Limits

### Daemon API Queries

#### Jobs List
- **Default**: `50` jobs
- **Maximum**: `500` jobs
- **File**: `daemon/api/routes.py` - `/api/jobs` endpoint
- **Query Parameter**: `?limit=50`

#### Database Table Rows
- **Default**: `100` rows
- **Maximum**: `500` rows
- **File**: `daemon/api/routes.py` - `/api/admin/database/table/{name}` endpoint
- **Query Parameter**: `?limit=100&offset=0`

#### Authors List
- **Default**: `100` authors
- **Maximum**: `500` authors
- **File**: `daemon/api/routes.py` - `/api/authors` endpoint
- **Query Parameter**: `?limit=100`

#### YouTube Search Results
- **Default**: `10` results
- **Maximum**: `50` results
- **File**: `daemon/models/schemas.py` - `YouTubeSearchRequest` schema
- **Rationale**: YouTube Data API quota management

#### Monitor Events
- **Default**: `50` events
- **Maximum**: `200` events
- **File**: `daemon/api/routes.py` - `/api/monitor/events` endpoint

### GetReceipts Search API

#### Search Endpoints (Claims, People, Jargon, Concepts)
- **Default**: `50` results (updated from 10)
- **Files**:
  - `src/app/api/search/claims/route.ts`
  - `src/app/api/search/people/route.ts`
  - `src/app/api/search/jargon/route.ts`
  - `src/app/api/search/concepts/route.ts`
- **Query Parameter**: `?q=search&limit=50`

#### Questions List
- **Default**: `50` results (updated from 20)
- **File**: `src/app/api/questions/route.ts`

#### Entity Linker Components
- **Default**: `50` results (updated from 10)
- **Files**:
  - `src/components/PersonLinker.tsx`
  - `src/components/EntityLinker.tsx`
- **Use Case**: Autocomplete dropdowns in UI

#### Edit Proposals & Arbitration
- **Default**: `20` results
- **Maximum**: `100` results (capped)
- **Files**:
  - `src/app/api/edit-proposals/route.ts`
  - `src/app/api/arbitration/route.ts`

#### Network Queries
- **Paradigms/Questions**: `200` results
- **People Network**: `100` results
- **Files**:
  - `src/app/api/paradigms/question-web/route.ts`
  - `src/app/api/paradigms/people-network/route.ts`

---

## 🎯 Recommendation: Keep These Limits

The following limits serve important purposes and should NOT be increased:

### Data Quality
- **Claim text length**: `10000` characters
  - Prevents database bloat
  - Maintains claim readability
  - Forces atomic claim creation

### API Quota Management
- **YouTube search results**: `50` maximum
  - YouTube Data API has strict quotas
  - 10,000 units/day = ~100 searches
  - Each search costs ~100 quota units

### Performance
- **Database query limits**: `500` maximum
  - Prevents slow queries
  - Maintains API responsiveness
  - Pagination encourages efficient data access

---

## 🔧 How to Change Limits

### Single Limit Change
1. Update the relevant file(s) listed above
2. Update this documentation
3. Update CHANGELOG.md
4. Test the change thoroughly
5. Update flowchart if the limit appears there

### Multiple Limit Changes
Use find-and-replace across the codebase:
```bash
# Example: Change RSS max from 9999 to 50000
grep -r "9999" daemon/ src/ --include="*.py" --include="*.ts" --include="*.tsx"
```

### Environment-Specific Limits
Consider using environment variables for limits that might differ between dev/prod:
```python
MAX_RSS_EPISODES = int(os.getenv('MAX_RSS_EPISODES', '9999'))
```

---

## 📝 Audit Trail

### December 29, 2025 - Initial Generous Limits
- RSS episodes: 500 → 9999 (max 99999)
- Records per upload: 2000 → 99999
- Rate limit: 20/hour → 9999/hour → 99999/hour
- Search results: 10-20 → 50
- **Rationale**: Remove friction during initial rollout, can tighten later based on actual usage patterns

### Future Recommendations
Monitor actual usage for 30-60 days, then consider:
- **Rate limiting**: Adjust based on legitimate vs. abusive patterns
- **Upload size**: Look for actual distribution of upload sizes
- **Search results**: Analyze pagination usage
- **RSS feeds**: Check if anyone actually needs >1000 episodes

---

## 🚨 Security Considerations

### Why Some Limits Must Stay
1. **API Quotas**: External services (YouTube, etc.) have hard limits
2. **Database Performance**: Very large queries can DOS the database
3. **Memory Usage**: Unbounded caches can crash the daemon
4. **Data Quality**: Some limits ensure usability of the data

### Monitoring Recommendations
Set up alerts for:
- Uploads approaching the 99999 record limit (might be accidental)
- Users hitting rate limits frequently (might indicate automation)
- Searches consistently returning the maximum 50 results (might need better search)
- RSS feeds with >10000 episodes (extremely rare, might be malformed feed)

---

## 📊 Quick Reference Table

| Limit Type | Value | Max | Purpose | Can Increase? |
|------------|-------|-----|---------|---------------|
| RSS Episodes | 9999 | 99999 | Feed ingestion | ✅ Yes |
| Upload Records | 99999 | - | Single upload | ⚠️ Carefully |
| Upload Rate | 99999/hr | - | Spam prevention | ⚠️ Carefully |
| Claim Length | 10000 | - | Data quality | ❌ No |
| Search Results | 50 | - | UI/Performance | ✅ Yes |
| Job History | 500 | - | Memory management | ⚠️ Consider DB |
| YouTube Search | 10 | 50 | API quota | ❌ No |
| Monitor Events | 100 | - | Memory management | ⚠️ Consider logs |
| Query Limits | 50-500 | - | Performance | ⚠️ Carefully |

**Legend**:
- ✅ Yes: Safe to increase if needed
- ⚠️ Carefully: Consider implications first
- ❌ No: Keep current limit for good reason

---

## 📞 Support

If you need to adjust limits beyond these recommendations, consider:
1. **Usage analysis**: Monitor actual usage patterns first
2. **Performance testing**: Test with realistic data volumes
3. **Gradual rollout**: Increase limits incrementally
4. **User feedback**: Ask heavy users about pain points

---

**Questions or concerns?** File an issue or contact the development team.

