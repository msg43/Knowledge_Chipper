# Knowledge Chipper Migration Guide

This guide helps you migrate from the old version to the new refactored architecture.

## Quick Start Migration

### 1. Backup Your Data
```bash
# Backup your database
cp knowledge_system.db knowledge_system.db.backup

# Backup your output directory
cp -r output/ output_backup/
```

### 2. Run Database Migrations
```bash
# The migrations will update your database schema
python -m knowledge_system migrate
```

### 3. Update Configuration
If you have Supabase (optional):
```yaml
# config/settings.yaml
supabase_url: "https://your-project.supabase.co"
supabase_key: "your-anon-key"
```

## What's Changed

### Database Changes
- **Table Renamed**: `videos` → `media_sources`
- **New Tables**: 
  - `claim_sources` and `supporting_evidence` (split from `evidence_spans`)
  - `claim_types`, `quality_criteria`, `claim_clusters`
- **New Columns**: All tables now have sync columns for cloud backup

### Terminology Updates
- "Belief statements" → "Claims"
- `beliefs.yaml` → `claims.yaml`
- "Video" → "Media Source" (supports all document types)

### New Features Available
1. **Document Processing**: Upload PDFs, Word docs, and more
2. **Speaker Attribution**: Manage speaker names in transcripts
3. **Cloud Sync**: Optional backup to Supabase
4. **Better Chunking**: Smarter text splitting for large documents

## Code Migration (For Developers)

### Import Changes
```python
# Old
from knowledge_system.database import Video

# New
from knowledge_system.database import MediaSource
```

### Field Changes
```python
# Old
video_id = "abc123"

# New
media_id = "abc123"
```

### MOC Changes
```python
# Old
moc_data.beliefs

# New  
moc_data.claims
```

## Troubleshooting

### Issue: "Table videos not found"
**Solution**: Run the migrations - the table was renamed to `media_sources`

### Issue: "No module named Video"
**Solution**: Update imports to use `MediaSource` instead

### Issue: Old files reference video_id
**Solution**: The system maintains compatibility - old references still work

## Getting Help

1. Check the logs in `logs/` directory
2. Run tests: `python comprehensive_test_suite.py`
3. See full documentation: [README.md](README.md)

## No Data Loss

The migration process preserves all your existing data. The old `videos` table is backed up as `videos_old` and all data is migrated to the new structure.
