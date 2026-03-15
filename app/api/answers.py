from fastapi import APIRouter, HTTPException
from app.core.models import SubmitAnswerRequest, SubmitAnswerResponse, StudentAnswer
from app.db.mongodb import get_db
from app.services.adaptive import update_student_level, get_student_stats

router = APIRouter()


@router.post("/submit-answer", response_model=SubmitAnswerResponse)
async def submit_answer(req: SubmitAnswerRequest):
    """
    Submit a student's answer.
    - Checks correctness
    - Updates adaptive difficulty level
    - Returns result + new difficulty label
    """
    db = get_db()

    question = await db.questions.find_one({"question_id": req.question_id})
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    correct_answer = question["answer"].strip().lower()
    submitted = req.selected_answer.strip().lower()
    is_correct = submitted == correct_answer

    answer = StudentAnswer(
        student_id=req.student_id,
        question_id=req.question_id,
        selected_answer=req.selected_answer,
        is_correct=is_correct,
    )
    await db.answers.insert_one(answer.model_dump())

    topic = question.get("topic") or question.get("subject") or "General"
    new_level = await update_student_level(req.student_id, topic, is_correct)

    from app.services.adaptive import level_to_label
    new_difficulty = level_to_label(new_level)
    stats = await get_student_stats(req.student_id)

    return SubmitAnswerResponse(
        answer_id=answer.answer_id,
        is_correct=is_correct,
        correct_answer=question["answer"],
        new_difficulty=new_difficulty,
        student_score=stats,
    )


@router.get("/students/{student_id}/stats")
async def student_stats(student_id: str):
    """Get a student's performance stats and current difficulty levels per topic."""
    return await get_student_stats(student_id)


@router.get("/students/{student_id}/answers")
async def student_answers(student_id: str, limit: int = 20):
    """Get a student's answer history."""
    db = get_db()
    answers = await db.answers.find(
        {"student_id": student_id}, {"_id": 0}
    ).sort("submitted_at", -1).limit(limit).to_list(limit)
    return {"answers": answers, "count": len(answers)}
