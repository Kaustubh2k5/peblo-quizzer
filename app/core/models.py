from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
import uuid


def new_id():
    return str(uuid.uuid4())


# ── Source document ──────────────────────────────────────────────
class SourceDocument(BaseModel):
    source_id: str = Field(default_factory=new_id)
    filename: str
    grade: Optional[int] = None
    subject: Optional[str] = None
    status: Literal["pending", "processing", "done", "error"] = "pending"
    chunk_count: int = 0
    question_count: int = 0
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    error: Optional[str] = None


# ── Content chunk ─────────────────────────────────────────────────
class ContentChunk(BaseModel):
    chunk_id: str = Field(default_factory=new_id)
    source_id: str
    grade: Optional[int] = None
    subject: Optional[str] = None
    topic: Optional[str] = None
    text: str
    chunk_index: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Quiz question ─────────────────────────────────────────────────
class QuizQuestion(BaseModel):
    question_id: str = Field(default_factory=new_id)
    chunk_id: str
    source_id: str
    question: str
    type: Literal["mcq", "true_false", "fill_blank"]
    options: Optional[List[str]] = None
    answer: str
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    topic: Optional[str] = None
    subject: Optional[str] = None
    grade: Optional[int] = None
    validated: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Student answer ────────────────────────────────────────────────
class StudentAnswer(BaseModel):
    answer_id: str = Field(default_factory=new_id)
    student_id: str
    question_id: str
    selected_answer: str
    is_correct: Optional[bool] = None
    submitted_at: datetime = Field(default_factory=datetime.utcnow)


# ── Student profile (adaptive state) ─────────────────────────────
class StudentProfile(BaseModel):
    student_id: str
    difficulty_levels: dict = Field(default_factory=dict)  # topic -> float 0..1
    total_answered: int = 0
    total_correct: int = 0
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── API request/response models ───────────────────────────────────
class IngestResponse(BaseModel):
    source_id: str
    filename: str
    status: str
    message: str


class GenerateQuizRequest(BaseModel):
    source_id: str
    questions_per_chunk: Optional[int] = 3


class GenerateQuizResponse(BaseModel):
    source_id: str
    questions_generated: int
    message: str


class QuizQueryParams(BaseModel):
    topic: Optional[str] = None
    difficulty: Optional[Literal["easy", "medium", "hard"]] = None
    subject: Optional[str] = None
    grade: Optional[int] = None
    limit: int = 10


class SubmitAnswerRequest(BaseModel):
    student_id: str
    question_id: str
    selected_answer: str


class SubmitAnswerResponse(BaseModel):
    answer_id: str
    is_correct: bool
    correct_answer: str
    explanation: Optional[str] = None
    new_difficulty: str
    student_score: dict
