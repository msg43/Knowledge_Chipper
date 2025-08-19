# HCE Rollback Strategy

## Overview
This document outlines the rollback procedures for the HCE (Hybrid Claim Extractor) replacement in case critical issues arise after deployment.

## Rollback Triggers
Consider rollback if any of these occur:
- Critical performance degradation (>5x slower than legacy)
- Data corruption or loss
- UI completely broken
- Unrecoverable errors in >10% of operations
- User revolt or major complaints

## Rollback Levels

### Level 1: Emergency Override (Immediate)
**Time: < 5 minutes**

1. Set environment variable:
   ```bash
   export USE_LEGACY_SUMMARIZER=1
   ```

2. Restart application

Note: This requires keeping legacy code paths available.

### Level 2: Code Revert (Quick)
**Time: < 30 minutes**

1. Identify the HCE merge commit:
   ```bash
   git log --oneline | grep "HCE replacement"
   ```

2. Revert the changes:
   ```bash
   git revert <commit-hash>
   git push origin main
   ```

3. Redeploy application

### Level 3: Full Database Rollback (Careful)
**Time: 1-2 hours**

1. Stop all services
2. Backup current database
3. Restore from pre-HCE backup
4. Revert code changes
5. Restart services

## Pre-Deployment Checklist

### Code Preservation
- [x] Legacy processors renamed to `*_legacy.py`
- [ ] Emergency override flag implemented
- [ ] Legacy import paths documented

### Database Safety
- [x] Compatibility views created
- [ ] Database backup before migration
- [ ] Migration rollback script ready

### Testing
- [ ] Full system backup created
- [ ] Rollback procedure tested in staging
- [ ] Recovery time measured

## Rollback Procedures

### Step 1: Assess the Situation
1. Identify the specific issue
2. Determine affected users/data
3. Choose appropriate rollback level

### Step 2: Communicate
1. Notify users of issues
2. Provide ETA for resolution
3. Document incident

### Step 3: Execute Rollback

#### For Code Rollback:
```bash
# On main branch
git checkout main
git pull origin main

# Create rollback branch
git checkout -b hotfix/rollback-hce

# Revert HCE commits
git revert --no-commit c5f0e07..HEAD
git commit -m "Rollback: Revert HCE implementation due to [ISSUE]"

# Test locally
pytest tests/

# Push and create PR
git push origin hotfix/rollback-hce
```

#### For Database Rollback:
```bash
# Stop services
systemctl stop knowledge-chipper

# Backup current state
sqlite3 knowledge_system.db ".backup knowledge_system_hce_failed.db"

# Restore pre-HCE backup
cp backups/knowledge_system_pre_hce.db knowledge_system.db

# Restart services
systemctl start knowledge-chipper
```

### Step 4: Post-Rollback
1. Verify system functionality
2. Monitor for issues
3. Plan fix for HCE issues
4. Document lessons learned

## Data Recovery

### If HCE Data Was Written:
The compatibility views ensure legacy code can read HCE data:
- `summaries` table still exists
- MOC data accessible via views
- File outputs remain compatible

### If Migration Failed:
1. Check migration logs
2. Manually fix schema issues
3. Re-run migration with fixes

## Prevention Strategies

### Before Deployment:
1. Test rollback procedure in staging
2. Create automated rollback script
3. Ensure monitoring alerts work
4. Have team ready for deployment

### During Deployment:
1. Deploy to small user group first
2. Monitor metrics closely
3. Have rollback command ready
4. Keep communication channels open

## Recovery Metrics

Target recovery times:
- Emergency override: < 5 minutes
- Code rollback: < 30 minutes  
- Full rollback: < 2 hours

Acceptable data loss:
- None for existing data
- New HCE features may be lost

## Contact Information

In case of emergency:
- Primary: [Dev Lead]
- Secondary: [Ops Team]
- Escalation: [CTO]

## Appendix: Useful Commands

```bash
# Check current branch
git branch --show-current

# View recent commits
git log --oneline -10

# Check database schema
sqlite3 knowledge_system.db ".schema"

# Test legacy processors
python -c "from knowledge_system.processors.summarizer_legacy import SummarizerProcessor"

# Run smoke tests
make test-smoke
```
