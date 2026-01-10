#!/bin/bash
# Monitor extraction job until completion

if [ -z "$1" ]; then
    echo "Usage: ./monitor_extraction.sh JOB_ID"
    echo "Getting latest job..."
    JOB_ID=$(curl -s "http://127.0.0.1:8765/api/jobs?limit=1" | python3 -c "import sys, json; print(json.load(sys.stdin)['jobs'][0]['job_id'])")
    echo "Monitoring job: $JOB_ID"
else
    JOB_ID="$1"
fi

echo "🚀 Monitoring extraction job: $JOB_ID"
echo ""

for i in {1..300}; do 
  RESULT=$(curl -s "http://127.0.0.1:8765/api/jobs/$JOB_ID")
  
  STATUS=$(echo "$RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])" 2>/dev/null)
  PROGRESS=$(echo "$RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin)['progress'])" 2>/dev/null)
  STAGE=$(echo "$RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin)['current_stage'])" 2>/dev/null)
  CLAIMS=$(echo "$RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('claims_count', 'N/A'))" 2>/dev/null)
  TITLE=$(echo "$RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('title', 'Unknown')[:60])" 2>/dev/null)
  
  printf "\r[%3d] %-12s | %5s%% | %-40s | Claims: %-4s" "$i" "$STATUS" "$PROGRESS" "${STAGE:0:40}" "$CLAIMS"
  
  if [ "$STATUS" = "completed" ]; then
    echo ""
    echo ""
    echo "🎉 ✅ EXTRACTION COMPLETED SUCCESSFULLY!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Title: $TITLE"
    echo "$RESULT" | python3 -c "import sys, json; d=json.load(sys.stdin); print(f\"Claims: {d.get('claims_count', 0)}\"); print(f\"Transcript: {d.get('transcript_length', 0)} chars\"); print(f\"Uploaded: {d.get('uploaded_to_getreceipts', False)}\"); print(f\"Episode Code: {d.get('getreceipts_episode_code', 'N/A')}\")"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "📝 Review at: https://www.getreceipts.org/dashboard/review/drafts"
    break
  elif [ "$STATUS" = "failed" ]; then
    echo ""
    echo ""
    echo "❌ EXTRACTION FAILED"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "$RESULT" | python3 -c "import sys, json; d=json.load(sys.stdin); print(f\"Error: {d.get('error', 'Unknown')[:500]}\")"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    break
  fi
  
  sleep 3
done

echo ""
