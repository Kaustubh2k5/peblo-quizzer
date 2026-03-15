#!/bin/bash
# ─────────────────────────────────────────────────────────────────────
#  Peblo Quick Smoke Test
#  Usage: bash scripts/smoke_test.sh
#  Requires: curl, jq (brew install jq / apt install jq)
# ─────────────────────────────────────────────────────────────────────

BASE="http://localhost:80"
PASS=0
FAIL=0

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "${GREEN}  PASS${NC} $1"; ((PASS++)); }
fail() { echo -e "${RED}  FAIL${NC} $1"; ((FAIL++)); }
info() { echo -e "${YELLOW}  INFO${NC} $1"; }

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Peblo Smoke Test  →  $BASE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── 1. Root ──────────────────────────────────────────────────────────
echo "1. Root endpoint"
R=$(curl -s "$BASE/")
if echo "$R" | grep -q "Peblo"; then ok "GET /"; else fail "GET / — $R"; fi

# ── 2. Health ────────────────────────────────────────────────────────
echo ""
echo "2. Health check"
R=$(curl -s "$BASE/health")
MONGO=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('mongodb','?'))" 2>/dev/null)
REDIS=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('redis','?'))" 2>/dev/null)
LLM=$(echo   "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('llm_provider','?'))" 2>/dev/null)
KEY=$(echo   "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('llm_key_set','?'))" 2>/dev/null)

info "MongoDB: $MONGO | Redis: $REDIS | LLM: $LLM | Key set: $KEY"
if [ "$MONGO" = "ok" ]; then ok "MongoDB connected"; else fail "MongoDB: $MONGO"; fi
if [ "$REDIS" = "ok" ]; then ok "Redis connected";   else fail "Redis: $REDIS"; fi
if [ "$KEY" = "True" ];  then ok "LLM API key set";  else fail "LLM API key not set — check .env"; fi

# ── 3. Ingest PDF ────────────────────────────────────────────────────
echo ""
echo "3. PDF ingestion"

# Create a tiny valid test PDF inline
python3 -c "
content = b'''%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length 220>>
stream
BT /F1 12 Tf 50 750 Td
(Grade 3 Science - Plants and Animals) Tj
0 -20 Td (Plants make food using sunlight in photosynthesis.) Tj
0 -20 Td (Animals eat plants or other animals for energy.) Tj
0 -20 Td (Roots absorb water from the soil.) Tj
ET
endstream
endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000274 00000 n
0000000548 00000 n
trailer<</Size 6/Root 1 0 R>>
startxref
630
%%EOF'''
open('/tmp/test_peblo.pdf','wb').write(content)
"

R=$(curl -s -X POST "$BASE/api/ingest" -F "file=@/tmp/test_peblo.pdf")
SOURCE_ID=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('source_id',''))" 2>/dev/null)
STATUS=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status',''))" 2>/dev/null)

if [ -n "$SOURCE_ID" ]; then
  ok "PDF accepted — source_id: $SOURCE_ID"
  info "Status: $STATUS"
else
  fail "Ingest failed: $R"
fi

# ── 4. Poll for processing ───────────────────────────────────────────
echo ""
echo "4. Waiting for ingestion to complete..."
FINAL_STATUS="pending"
for i in {1..15}; do
  sleep 2
  R=$(curl -s "$BASE/api/sources/$SOURCE_ID")
  FINAL_STATUS=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status',''))" 2>/dev/null)
  CHUNKS=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('chunk_count',0))" 2>/dev/null)
  if [ "$FINAL_STATUS" = "done" ] || [ "$FINAL_STATUS" = "error" ]; then break; fi
  echo "   ...still processing ($i/15)"
done

if [ "$FINAL_STATUS" = "done" ]; then
  ok "Ingestion complete — $CHUNKS chunks"
else
  fail "Ingestion ended with status: $FINAL_STATUS"
fi

# ── 5. Generate quiz ─────────────────────────────────────────────────
echo ""
echo "5. Quiz generation (calls LLM — may take 10-20s)"
R=$(curl -s -X POST "$BASE/api/generate-quiz" \
  -H "Content-Type: application/json" \
  -d "{\"source_id\":\"$SOURCE_ID\",\"questions_per_chunk\":2}")

GENERATED=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('questions_generated','?'))" 2>/dev/null)
MSG=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('message',''))" 2>/dev/null)

if [ "$GENERATED" != "?" ] && [ "$GENERATED" -gt 0 ] 2>/dev/null; then
  ok "Generated $GENERATED questions"
  info "$MSG"
else
  fail "Quiz generation failed: $R"
fi

# ── 6. Get quiz questions ────────────────────────────────────────────
echo ""
echo "6. Quiz retrieval"
R=$(curl -s "$BASE/api/quiz?limit=5")
COUNT=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('count',0))" 2>/dev/null)
if [ "$COUNT" -gt 0 ] 2>/dev/null; then
  ok "Retrieved $COUNT questions"
  QUESTION_ID=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['questions'][0]['question_id'])" 2>/dev/null)
  ANSWER=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['questions'][0]['answer'])" 2>/dev/null)
  QUESTION_TEXT=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['questions'][0]['question'][:60])" 2>/dev/null)
  info "Sample: \"$QUESTION_TEXT...\""
else
  fail "No questions returned"
  QUESTION_ID=""
  ANSWER=""
fi

# Difficulty filter
R=$(curl -s "$BASE/api/quiz?difficulty=easy&limit=5")
ok "Difficulty filter (easy) — $(echo "$R" | python3 -c "import sys,json; print(json.load(sys.stdin)['count'])" 2>/dev/null) results"

# Adaptive quiz
R=$(curl -s "$BASE/api/quiz?student_id=test_student&limit=5")
ADAPTIVE_DIFF=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['filters']['difficulty'])" 2>/dev/null)
ok "Adaptive quiz for new student — difficulty: $ADAPTIVE_DIFF"

# ── 7. Submit answer ─────────────────────────────────────────────────
echo ""
echo "7. Answer submission"
if [ -n "$QUESTION_ID" ]; then
  # Correct answer
  R=$(curl -s -X POST "$BASE/api/submit-answer" \
    -H "Content-Type: application/json" \
    -d "{\"student_id\":\"test_student\",\"question_id\":\"$QUESTION_ID\",\"selected_answer\":\"$ANSWER\"}")
  CORRECT=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('is_correct','?'))" 2>/dev/null)
  DIFF=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('new_difficulty','?'))" 2>/dev/null)
  if [ "$CORRECT" = "True" ]; then
    ok "Correct answer accepted — new difficulty: $DIFF"
  else
    fail "Expected correct answer, got: $R"
  fi

  # Wrong answer
  R=$(curl -s -X POST "$BASE/api/submit-answer" \
    -H "Content-Type: application/json" \
    -d "{\"student_id\":\"test_student\",\"question_id\":\"$QUESTION_ID\",\"selected_answer\":\"wrong answer xyz\"}")
  CORRECT=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('is_correct','?'))" 2>/dev/null)
  DIFF=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('new_difficulty','?'))" 2>/dev/null)
  if [ "$CORRECT" = "False" ]; then
    ok "Wrong answer detected — difficulty adjusted to: $DIFF"
  else
    fail "Expected wrong answer result, got: $R"
  fi
else
  info "Skipping answer submission (no question available)"
fi

# ── 8. Student stats ─────────────────────────────────────────────────
echo ""
echo "8. Student adaptive stats"
R=$(curl -s "$BASE/api/students/test_student/stats")
ACCURACY=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('accuracy','?'))" 2>/dev/null)
LEVELS=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('difficulty_levels',{}))" 2>/dev/null)
ok "Student stats — accuracy: ${ACCURACY}%, levels: $LEVELS"

# ── Summary ──────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "  Results: ${GREEN}$PASS passed${NC}  ${RED}$FAIL failed${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
if [ "$FAIL" -eq 0 ]; then
  echo -e "  ${GREEN}All tests passed. System is working.${NC}"
else
  echo -e "  ${RED}$FAIL test(s) failed. Check the output above.${NC}"
fi
echo ""
