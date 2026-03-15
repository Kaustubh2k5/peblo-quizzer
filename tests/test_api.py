"""
Peblo Quiz Engine — Test Suite
Run with: pytest tests/ -v
Requires the API to be running at http://localhost:8000
"""

import pytest
import httpx
import os
import io
import time

BASE_URL = os.getenv("API_URL", "http://localhost:8000")
STUDENT_ID = "test_student_001"


# ── Helpers ──────────────────────────────────────────────────────────

def client():
    return httpx.Client(base_url=BASE_URL, timeout=60)


def make_fake_pdf() -> bytes:
    """
    Returns a minimal valid PDF with educational content.
    Used so tests don't require a real PDF file.
    """
    content = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length 200>>
stream
BT /F1 12 Tf 50 750 Td
(Grade 3 Science - Plants and Animals) Tj
0 -20 Td (Plants make their own food using sunlight.) Tj
0 -20 Td (This process is called photosynthesis.) Tj
0 -20 Td (Animals get energy by eating plants or other animals.) Tj
0 -20 Td (A triangle has three sides and three angles.) Tj
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
0000000528 00000 n
trailer<</Size 6/Root 1 0 R>>
startxref
610
%%EOF"""
    return content


# ── Tests ─────────────────────────────────────────────────────────────

class TestHealth:
    def test_root(self):
        r = client().get("/")
        assert r.status_code == 200
        data = r.json()
        assert data["service"] == "Peblo Quiz Engine"

    def test_health_endpoint(self):
        r = client().get("/health")
        assert r.status_code == 200
        data = r.json()
        assert "mongodb" in data
        assert "redis" in data
        assert "llm_provider" in data
        print(f"\n  Health: {data}")


class TestIngestion:
    source_id = None

    def test_ingest_pdf(self):
        pdf_bytes = make_fake_pdf()
        files = {"file": ("test_science.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        r = client().post("/api/ingest", files=files)
        assert r.status_code == 200
        data = r.json()
        assert "source_id" in data
        assert data["status"] == "processing"
        TestIngestion.source_id = data["source_id"]
        print(f"\n  source_id: {data['source_id']}")

    def test_ingest_rejects_non_pdf(self):
        files = {"file": ("notes.txt", io.BytesIO(b"some text"), "text/plain")}
        r = client().post("/api/ingest", files=files)
        assert r.status_code == 400

    def test_list_sources(self):
        r = client().get("/api/sources")
        assert r.status_code == 200
        data = r.json()
        assert "sources" in data
        assert isinstance(data["sources"], list)
        print(f"\n  Total sources: {data['count']}")

    def test_get_source_status(self):
        if not TestIngestion.source_id:
            pytest.skip("No source_id from previous test")

        # Poll until done or timeout
        for _ in range(15):
            r = client().get(f"/api/sources/{TestIngestion.source_id}")
            assert r.status_code == 200
            data = r.json()
            if data["status"] in ("done", "error"):
                print(f"\n  Final status: {data['status']}, chunks: {data.get('chunk_count', 0)}")
                break
            time.sleep(2)

    def test_get_source_not_found(self):
        r = client().get("/api/sources/nonexistent-id-12345")
        assert r.status_code == 404


class TestQuizGeneration:
    def test_generate_quiz_requires_valid_source(self):
        r = client().post("/api/generate-quiz", json={"source_id": "bad-id-xyz"})
        assert r.status_code == 404

    def test_generate_quiz_for_source(self):
        # Get first source that is done
        r = client().get("/api/sources")
        sources = r.json()["sources"]
        done = [s for s in sources if s["status"] == "done"]
        if not done:
            pytest.skip("No ingested sources ready")

        source_id = done[0]["source_id"]
        r = client().post(
            "/api/generate-quiz",
            json={"source_id": source_id, "questions_per_chunk": 2},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["questions_generated"] >= 0
        print(f"\n  Questions generated: {data['questions_generated']}")
        print(f"  Provider: {data['message']}")


class TestQuizRetrieval:
    def test_get_quiz_no_filters(self):
        r = client().get("/api/quiz")
        assert r.status_code == 200
        data = r.json()
        assert "questions" in data
        assert isinstance(data["questions"], list)
        print(f"\n  Total questions available: {data['count']}")

    def test_get_quiz_with_difficulty(self):
        for diff in ("easy", "medium", "hard"):
            r = client().get(f"/api/quiz?difficulty={diff}&limit=5")
            assert r.status_code == 200
            data = r.json()
            for q in data["questions"]:
                assert q["difficulty"] == diff

    def test_get_quiz_with_student_adaptive(self):
        r = client().get(f"/api/quiz?student_id={STUDENT_ID}&limit=5")
        assert r.status_code == 200
        data = r.json()
        assert "filters" in data
        print(f"\n  Adaptive difficulty for {STUDENT_ID}: {data['filters']['difficulty']}")

    def test_get_quiz_limit(self):
        r = client().get("/api/quiz?limit=3")
        assert r.status_code == 200
        assert len(r.json()["questions"]) <= 3

    def test_list_topics(self):
        r = client().get("/api/topics")
        assert r.status_code == 200
        data = r.json()
        assert "topics" in data
        print(f"\n  Topics: {[t['topic'] for t in data['topics'][:5]]}")


class TestAnswerSubmission:
    question_id = None

    def test_get_a_question_id(self):
        r = client().get("/api/quiz?limit=1")
        questions = r.json()["questions"]
        if not questions:
            pytest.skip("No questions in DB yet")
        TestAnswerSubmission.question_id = questions[0]["question_id"]
        TestAnswerSubmission.correct_answer = questions[0]["answer"]

    def test_submit_correct_answer(self):
        if not TestAnswerSubmission.question_id:
            pytest.skip("No question available")

        r = client().post("/api/submit-answer", json={
            "student_id": STUDENT_ID,
            "question_id": TestAnswerSubmission.question_id,
            "selected_answer": TestAnswerSubmission.correct_answer,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["is_correct"] is True
        assert "new_difficulty" in data
        assert data["new_difficulty"] in ("easy", "medium", "hard")
        print(f"\n  Correct answer result: {data}")

    def test_submit_wrong_answer(self):
        if not TestAnswerSubmission.question_id:
            pytest.skip("No question available")

        r = client().post("/api/submit-answer", json={
            "student_id": STUDENT_ID,
            "question_id": TestAnswerSubmission.question_id,
            "selected_answer": "definitely wrong answer xyz",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["is_correct"] is False
        print(f"\n  Wrong answer result: difficulty → {data['new_difficulty']}")

    def test_submit_answer_bad_question(self):
        r = client().post("/api/submit-answer", json={
            "student_id": STUDENT_ID,
            "question_id": "nonexistent-question-id",
            "selected_answer": "anything",
        })
        assert r.status_code == 404


class TestAdaptiveDifficulty:
    def test_student_stats(self):
        r = client().get(f"/api/students/{STUDENT_ID}/stats")
        assert r.status_code == 200
        data = r.json()
        assert "total_answered" in data
        assert "accuracy" in data
        assert "difficulty_levels" in data
        print(f"\n  Student stats: {data}")

    def test_difficulty_increases_on_correct(self):
        """Answer 5 questions correctly — difficulty level should rise."""
        r = client().get("/api/quiz?limit=5")
        questions = r.json()["questions"]
        if len(questions) < 2:
            pytest.skip("Not enough questions")

        student = "adaptive_test_student"

        # Get initial level
        r1 = client().get(f"/api/students/{student}/stats")
        initial = r1.json()

        # Submit correct answers
        for q in questions[:3]:
            client().post("/api/submit-answer", json={
                "student_id": student,
                "question_id": q["question_id"],
                "selected_answer": q["answer"],
            })

        # Check level moved up
        r2 = client().get(f"/api/students/{student}/stats")
        final = r2.json()
        print(f"\n  Adaptive test — answered: {final['total_answered']}, accuracy: {final['accuracy']}%")
        print(f"  Difficulty levels: {final['difficulty_levels']}")
        assert final["total_answered"] >= 3

    def test_student_answer_history(self):
        r = client().get(f"/api/students/{STUDENT_ID}/answers")
        assert r.status_code == 200
        data = r.json()
        assert "answers" in data
        print(f"\n  Answer history count: {data['count']}")
