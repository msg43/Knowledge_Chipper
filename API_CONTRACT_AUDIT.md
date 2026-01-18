# API Contract Audit: Daemon ↔ Web

**Date:** January 17, 2026  
**Purpose:** Verify all daemon API endpoints are called by web client and vice versa

---

## Daemon Endpoints (Python FastAPI)

**Source:** `daemon/api/routes.py`

### ✅ ACTIVE - Called by Web Client

| Endpoint | Method | Client Method | Status |
|----------|--------|---------------|--------|
| `/api/health` | GET | `health()` | ✅ Active |
| `/api/process` | POST | `process()` | ✅ Active |
| `/api/process/batch` | POST | `processBatch()` | ✅ Active |
| `/api/jobs/{job_id}` | GET | `getJobStatus()` | ✅ Active |
| `/api/jobs` | GET | `listJobs()` | ✅ Active |
| `/api/jobs/{job_id}/retry` | POST | `retryJob()` | ✅ Active |
| `/api/jobs/{job_id}/cancel` | POST | `cancelJob()` | ✅ Active |
| `/api/jobs/{job_id}` | DELETE | `deleteJob()` | ✅ Active |
| `/api/jobs/bulk/retry` | POST | `bulkRetryJobs()` | ✅ Active |
| `/api/jobs/bulk/delete` | POST | `bulkDeleteJobs()` | ✅ Active |
| `/api/config` | GET | `getConfig()` | ✅ Active |
| `/api/config` | PATCH | `updateConfig()` | ✅ Active |
| `/api/config/api-keys` | GET | `getApiKeyStatus()` | ✅ Active |
| `/api/config/api-keys` | POST | `setApiKeys()` | ✅ Active |
| `/api/config/test-model-access` | POST | `testModelAccess()` | ✅ Active |
| `/api/config/whisper-models` | GET | `getWhisperModels()` | ✅ Active |
| `/api/config/models` | GET | `getAvailableModels()` | ✅ Active |
| `/api/config/device-status` | GET | `getDeviceStatus()` | ✅ Active |
| `/api/monitor/status` | GET | `getMonitorStatus()` | ✅ Active |
| `/api/monitor/config` | GET | `getMonitorConfig()` | ✅ Active |
| `/api/monitor/config` | PATCH | `updateMonitorConfig()` | ✅ Active |
| `/api/monitor/start` | POST | `startMonitor()` | ✅ Active |
| `/api/monitor/stop` | POST | `stopMonitor()` | ✅ Active |
| `/api/monitor/events` | GET | `getMonitorEvents()` | ✅ Active |
| `/api/monitor/events` | DELETE | `clearMonitorEvents()` | ✅ Active |
| `/api/monitor/browse` | GET | `browseFolders()` | ✅ Active |
| `/api/youtube/search` | POST | `searchYouTube()` | ✅ Active |
| `/api/updates/check` | GET | `checkForUpdates()` | ✅ Active |
| `/api/updates/install` | POST | `installUpdate()` | ✅ Active |
| `/api/updates/status` | GET | `getUpdateStatus()` | ✅ Active |
| `/api/feedback/stats` | GET | `getFeedbackStats()` | ✅ Active |
| `/api/feedback/sync` | POST | `syncFeedback()` | ✅ Active |
| `/api/feedback/queue-status` | GET | `getFeedbackQueueStatus()` | ✅ Active |
| `/api/config/feedback-reasons` | GET | `getFeedbackReasons()` | ✅ Active |

### ⚠️ POTENTIALLY UNUSED - Need Verification

| Endpoint | Method | Notes | Action Needed |
|----------|--------|-------|---------------|
| `/api/admin/database` | GET | HTML page for admin | Check if web links to it |
| `/api/admin/database/summary` | GET | Database summary stats | Check if web calls it |
| `/api/admin/database/table/{name}` | GET | Table data viewer | Check if web calls it |
| `/api/database/tables` | GET | List all tables | Check if web calls it |
| `/api/authors` | GET | List authors | Check if web calls it |
| `/api/authors` | POST | Create author | Check if web calls it |
| `/api/process/manual-metadata` | POST | Manual metadata entry | Check if web calls it |
| `/api/config/link-device` | POST | Link device to account | Check if web calls it |
| `/api/restart` | POST | Restart daemon | Check if web calls it |
| `/api/feedback/sync-status` | GET | Feedback sync status | Check if web calls it |

### 🔍 INVESTIGATION RESULTS

Checking daemon-client.ts for these endpoints...
