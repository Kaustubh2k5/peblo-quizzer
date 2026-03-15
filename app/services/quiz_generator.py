import json
import re
from typing import List
from app.core.models import ContentChunk, QuizQuestion
from app.llm.base import BaseLLMProvider

SYSTEM_PROMPT = """You are an expert educational content creator for K-12 students.
Your job is to generate clear, accurate quiz questions from educational text.
Always respond with valid JSON only — no markdown, no explanation, just the JSON array."""

QUESTION_PROMPT = """
Generate {n} quiz questions from the educational text below.

Rules:
- Mix question types: MCQ (multiple choice), true_false, fill_blank
- Difficulty: {difficulty}
- Questions must be answerable directly from the text
- For MCQ: provide exactly 4 options, one correct
- For true_false: answer must be "True" or "False"
- For fill_blank: use ___ in the question, answer is the missing word/phrase
- Keep language appropriate for grade {grade} students

Text:
\"\"\"
{text}
\"\"\"

Return ONLY a JSON array like this:
[
  {{
    "question": "How many sides does a triangle have?",
    "type": "mcq",
    "options": ["2", "3", "4", "5"],
    "answer": "3",
    "difficulty": "easy"
  }},
  {{
    "question": "A square has 4 equal sides.",
    "type": "true_false",
    "options": ["True", "False"],
    "answer": "True",
    "difficulty": "easy"
  }},
  {{
    "question": "A triangle has ___ sides.",
    "type": "fill_blank",
    "options": null,
    "answer": "three",
    "difficulty": "medium"
  }}
]
"""


def _parse_llm_response(raw: str) -> List[dict]:
    """Extract JSON array from LLM response robustly."""
    # Strip markdown code fences if present
    raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()

    # Find the JSON array
    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON array found in LLM response: {raw[:200]}")

    return json.loads(raw[start:end])


async def generate_questions_for_chunk(
    chunk: ContentChunk,
    llm: BaseLLMProvider,
    n: int = 3,
    difficulty: str = "mixed",
) -> List[QuizQuestion]:
    """Call the LLM to generate questions for one chunk."""
    grade_label = f"grade {chunk.grade}" if chunk.grade else "general"

    prompt = QUESTION_PROMPT.format(
        n=n,
        difficulty=difficulty,
        grade=grade_label,
        text=chunk.text[:800],  # cap to avoid token overflow
    )

    raw = await llm.generate(prompt, system=SYSTEM_PROMPT)
    items = _parse_llm_response(raw)

    questions = []
    for item in items:
        q_type = item.get("type", "mcq").lower()
        if q_type not in ("mcq", "true_false", "fill_blank"):
            q_type = "mcq"

        q = QuizQuestion(
            chunk_id=chunk.chunk_id,
            source_id=chunk.source_id,
            question=item.get("question", "").strip(),
            type=q_type,
            options=item.get("options"),
            answer=str(item.get("answer", "")).strip(),
            difficulty=item.get("difficulty", "medium"),
            topic=chunk.topic,
            subject=chunk.subject,
            grade=chunk.grade,
        )
        questions.append(q)

    return questions
