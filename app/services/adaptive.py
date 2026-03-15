"""
Adaptive difficulty engine.

Each student has a difficulty level per topic stored as a float 0.0 – 1.0.
  0.0 – 0.34  →  easy
  0.35 – 0.69 →  medium
  0.70 – 1.0  →  hard

On correct answer  → nudge level UP   (harder)
On wrong answer    → nudge level DOWN (easier)

The nudge uses a dampening factor so the level converges rather than oscillates.
"""

from datetime import datetime
from app.db.mongodb import get_db
from app.db.redis_client import get_redis
from app.core.models import StudentProfile
import json

LEVEL_KEY = "student:level:{student_id}:{topic}"
TTL = 3600 * 24  # cache for 24 hours

NUDGE_UP = 0.10
NUDGE_DOWN = 0.10


def level_to_label(level: float) -> str:
    if level < 0.35:
        return "easy"
    elif level < 0.70:
        return "medium"
    return "hard"


def label_to_level(label: str) -> float:
    return {"easy": 0.15, "medium": 0.52, "hard": 0.85}.get(label, 0.52)


async def get_student_level(student_id: str, topic: str) -> float:
    redis = await get_redis()
    key = LEVEL_KEY.format(student_id=student_id, topic=topic)
    cached = await redis.get(key)
    if cached is not None:
        return float(cached)

    db = get_db()
    profile = await db.students.find_one({"student_id": student_id})
    if profile and topic in profile.get("difficulty_levels", {}):
        level = profile["difficulty_levels"][topic]
    else:
        level = 0.15  # start easy for new students / new topics

    await redis.setex(key, TTL, str(level))
    return level


async def update_student_level(student_id: str, topic: str, is_correct: bool) -> float:
    current = await get_student_level(student_id, topic)

    if is_correct:
        new_level = min(1.0, current + NUDGE_UP * (1 - current))
    else:
        new_level = max(0.0, current - NUDGE_DOWN * current)

    # Persist to Redis cache
    redis = await get_redis()
    key = LEVEL_KEY.format(student_id=student_id, topic=topic)
    await redis.setex(key, TTL, str(new_level))

    # Persist to MongoDB
    db = get_db()
    await db.students.update_one(
        {"student_id": student_id},
        {
            "$set": {
                f"difficulty_levels.{topic}": new_level,
                "updated_at": datetime.utcnow(),
            },
            "$inc": {
                "total_answered": 1,
                "total_correct": 1 if is_correct else 0,
            },
        },
        upsert=True,
    )

    return new_level


async def get_difficulty_for_student(student_id: str, topic: str) -> str:
    level = await get_student_level(student_id, topic)
    return level_to_label(level)


async def get_student_stats(student_id: str) -> dict:
    db = get_db()
    profile = await db.students.find_one({"student_id": student_id}, {"_id": 0})
    if not profile:
        return {"student_id": student_id, "total_answered": 0, "total_correct": 0, "accuracy": 0, "difficulty_levels": {}}

    total = profile.get("total_answered", 0)
    correct = profile.get("total_correct", 0)
    accuracy = round(correct / total * 100, 1) if total > 0 else 0

    levels = profile.get("difficulty_levels", {})
    labeled = {topic: level_to_label(lvl) for topic, lvl in levels.items()}

    return {
        "student_id": student_id,
        "total_answered": total,
        "total_correct": correct,
        "accuracy": accuracy,
        "difficulty_levels": labeled,
    }
