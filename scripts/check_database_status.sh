#!/bin/bash
# Quick database status checker for ID unification testing

DB="knowledge_system.db"

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║              Database Status - ID Unification Testing               ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

if [ ! -f "$DB" ]; then
    echo "❌ Database not found: $DB"
    echo "   The app will create it on first launch."
    exit 1
fi

echo "📊 MEDIA SOURCES BY TYPE:"
echo "─────────────────────────────────────────────────────────────────────"
sqlite3 "$DB" "SELECT source_type, COUNT(*) as count FROM media_sources GROUP BY source_type;" | column -t -s '|'
echo ""

echo "📝 TOTAL RECORDS:"
echo "─────────────────────────────────────────────────────────────────────"
echo -n "MediaSources: "
sqlite3 "$DB" "SELECT COUNT(*) FROM media_sources;"
echo -n "Transcripts:  "
sqlite3 "$DB" "SELECT COUNT(*) FROM transcripts;"
echo -n "Summaries:    "
sqlite3 "$DB" "SELECT COUNT(*) FROM media_sources WHERE short_summary IS NOT NULL;"
echo -n "Segments:     "
sqlite3 "$DB" "SELECT COUNT(*) FROM segments;"
echo ""

echo "🔍 RECENT MEDIA SOURCES (Last 5):"
echo "─────────────────────────────────────────────────────────────────────"
sqlite3 "$DB" "SELECT source_id, source_type, title FROM media_sources ORDER BY created_at DESC LIMIT 5;" | while IFS='|' read -r id type title; do
    echo "  • [$type] $id"
    echo "    $title"
done
echo ""

echo "⚠️  POTENTIAL DUPLICATES (Same title, different source_id):"
echo "─────────────────────────────────────────────────────────────────────"
DUPES=$(sqlite3 "$DB" "SELECT title, COUNT(*) as count FROM media_sources GROUP BY title HAVING count > 1;")
if [ -z "$DUPES" ]; then
    echo "  ✅ No duplicates found!"
else
    echo "$DUPES" | while IFS='|' read -r title count; do
        echo "  ⚠️  \"$title\" appears $count times"
        sqlite3 "$DB" "SELECT '    ' || source_id || ' (' || source_type || ')' FROM media_sources WHERE title = '$title';"
    done
fi
echo ""

echo "🔗 ORPHANED RECORDS (Transcripts without valid source):"
echo "─────────────────────────────────────────────────────────────────────"
ORPHANS=$(sqlite3 "$DB" "SELECT COUNT(*) FROM transcripts t LEFT JOIN media_sources m ON t.source_id = m.source_id WHERE m.source_id IS NULL;")
if [ "$ORPHANS" = "0" ]; then
    echo "  ✅ No orphaned transcripts!"
else
    echo "  ⚠️  Found $ORPHANS orphaned transcript(s)"
fi
echo ""

echo "📋 SOURCE_ID FORMATS:"
echo "─────────────────────────────────────────────────────────────────────"
echo -n "YouTube (video_id):     "
sqlite3 "$DB" "SELECT COUNT(*) FROM media_sources WHERE source_type = 'youtube';"
echo -n "Audio (audio_*_hash):   "
sqlite3 "$DB" "SELECT COUNT(*) FROM media_sources WHERE source_id LIKE 'audio_%';"
echo -n "Document (doc_*_hash):  "
sqlite3 "$DB" "SELECT COUNT(*) FROM media_sources WHERE source_id LIKE 'doc_%';"
echo -n "Podcast (podcast_*):    "
sqlite3 "$DB" "SELECT COUNT(*) FROM media_sources WHERE source_id LIKE 'podcast_%';"
echo ""

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║                            Quick Commands                            ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""
echo "View all sources:"
echo "  sqlite3 $DB \"SELECT source_id, source_type, title FROM media_sources;\""
echo ""
echo "Check specific source:"
echo "  sqlite3 $DB \"SELECT * FROM media_sources WHERE source_id = 'VIDEO_ID';\""
echo ""
echo "View transcripts:"
echo "  sqlite3 $DB \"SELECT source_id, language, LENGTH(text) as text_length FROM transcripts;\""
echo ""
echo "Check summaries:"
echo "  sqlite3 $DB \"SELECT source_id, LENGTH(short_summary) as short_len, LENGTH(long_summary) as long_len FROM media_sources WHERE short_summary IS NOT NULL;\""
echo ""

