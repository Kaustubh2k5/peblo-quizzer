from fastapi import APIRouter, Query
from typing import Optional, Literal
from app.db.mongodb import get_db
import json
from app.db.redis_client import get_redis
router = APIRouter()

@router.get("/quiz")
async def get_quiz(
    topic: Optional[str] = Query(None, description="Filter by topic"),
    difficulty: Optional[Literal["easy", "medium", "hard"]] = Query(None),
    subject: Optional[str] = Query(None),
    grade: Optional[int] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    student_id: Optional[str] = Query(None, description="Auto-adjusts difficulty for this student"),
):


    db = get_db()

    if student_id and not difficulty:
        from app.services.adaptive import get_difficulty_for_student
        topic_key = topic or subject or "General"
        difficulty = await get_difficulty_for_student(student_id, topic_key)

    cache_key = f"quiz:{topic}:{difficulty}:{subject}:{grade}:{limit}"

    try:
        redis = await get_redis()
        cached = await redis.get(cache_key)
        if cached:
            result = json.loads(cached)
            result["cached"] = True
            return result
    except Exception:
        pass

    query = {}
    if topic:
        query["topic"] = {"$regex": topic, "$options": "i"}
    if difficulty:
        query["difficulty"] = difficulty
    if subject:
        query["subject"] = {"$regex": subject, "$options": "i"}
    if grade:
        query["grade"] = grade

    questions = await db.questions.find(query, {"_id": 0}).limit(limit).to_list(limit)

    result = {
        "questions": questions,
        "count": len(questions),
        "cached": False,
        "filters": {
            "topic": topic,
            "difficulty": difficulty,
            "subject": subject,
            "grade": grade,
            "student_id": student_id,
        },
    }

    if questions:
        try:
            redis = await get_redis()
            await redis.setex(cache_key, 300, json.dumps(result, default=str))
        except Exception:
            pass

    return result

@router.get("/quiz/{question_id}")
async def get_question(question_id: str):
    """Get a single question by ID."""
    db = get_db()
    q = await db.questions.find_one({"question_id": question_id}, {"_id": 0})
    if not q:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Question not found")
    return q


@router.get("/topics")
async def list_topics():
    """List all available topics and their question counts."""
    db = get_db()
    pipeline = [
        {"$group": {"_id": "$topic", "count": {"$sum": 1}, "subject": {"$first": "$subject"}}},
        {"$sort": {"count": -1}},
    ]
    topics = await db.questions.aggregate(pipeline).to_list(100)
    return {"topics": [{"topic": t["_id"], "question_count": t["count"], "subject": t["subject"]} for t in topics]}
