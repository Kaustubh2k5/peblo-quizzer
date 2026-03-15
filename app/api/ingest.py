from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from app.core.models import SourceDocument, IngestResponse, GenerateQuizRequest, GenerateQuizResponse
from app.core.config import settings
from app.db.mongodb import get_db
from app.services.ingestion import extract_text_from_pdf, build_chunks, guess_metadata
from app.services.quiz_generator import generate_questions_for_chunk
from app.llm.factory import get_llm_provider
from datetime import datetime
import asyncio
router = APIRouter()


async def _process_pdf(source_id: str, file_bytes: bytes, filename: str):
    """Background task: extract → chunk → store."""
    db = get_db()
    try:
        await db.sources.update_one(
            {"source_id": source_id},
            {"$set": {"status": "processing"}}
        )

        raw_text = extract_text_from_pdf(file_bytes)
        if not raw_text.strip():
            raise ValueError("No text could be extracted from this PDF")

        grade, subject, topic = guess_metadata(filename, raw_text)

        await db.sources.update_one(
            {"source_id": source_id},
            {"$set": {"grade": grade, "subject": subject}}
        )

        source = SourceDocument(
            source_id=source_id,
            filename=filename,
            grade=grade,
            subject=subject,
        )

        chunks = build_chunks(source, raw_text)

        for chunk in chunks:
            await db.chunks.insert_one(chunk.model_dump())

        await db.sources.update_one(
            {"source_id": source_id},
            {"$set": {"status": "done", "chunk_count": len(chunks)}}
        )

        print(f"[ingest] {filename} → {len(chunks)} chunks stored")

    except Exception as e:
        await db.sources.update_one(
            {"source_id": source_id},
            {"$set": {"status": "error", "error": str(e)}}
        )
        print(f"[ingest] ERROR processing {filename}: {e}")


@router.post("/ingest", response_model=IngestResponse)
async def ingest_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """Upload a PDF — extraction and chunking happen in the background."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    file_bytes = await file.read()
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(status_code=400, detail=f"File too large. Max {settings.MAX_FILE_SIZE_MB}MB")

    source = SourceDocument(filename=file.filename)
    db = get_db()
    await db.sources.insert_one(source.model_dump())

    background_tasks.add_task(_process_pdf, source.source_id, file_bytes, file.filename)

    return IngestResponse(
        source_id=source.source_id,
        filename=file.filename,
        status="processing",
        message="PDF accepted. Use GET /api/sources/{source_id} to check status.",
    )


@router.get("/sources")
async def list_sources():
    """List all ingested source documents."""
    db = get_db()
    docs = await db.sources.find({}, {"_id": 0}).to_list(100)
    return {"sources": docs, "count": len(docs)}


@router.get("/sources/{source_id}")
async def get_source(source_id: str):
    """Get ingestion status and metadata for a source."""
    db = get_db()
    doc = await db.sources.find_one({"source_id": source_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Source not found")
    return doc


@router.post("/generate-quiz", response_model=GenerateQuizResponse)
async def generate_quiz(req: GenerateQuizRequest):
    """Generate quiz questions from an ingested source using the LLM."""
    db = get_db()

    source = await db.sources.find_one({"source_id": req.source_id})
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if source["status"] != "done":
        raise HTTPException(status_code=400, detail=f"Source is not ready yet. Status: {source['status']}")

    chunks = await db.chunks.find({"source_id": req.source_id}, {"_id": 0}).to_list(10)
    if not chunks:
        raise HTTPException(status_code=400, detail="No chunks found for this source")

    llm = get_llm_provider()
    total_generated = 0
    n_per_chunk = req.questions_per_chunk or settings.QUESTIONS_PER_CHUNK



    for chunk_doc in chunks:
        from app.core.models import ContentChunk
        chunk = ContentChunk(**chunk_doc)
        try:
            questions = await generate_questions_for_chunk(chunk, llm, n=n_per_chunk)
            for q in questions:
                await db.questions.insert_one(q.model_dump())
            total_generated += len(questions)
        except Exception as e:
            print(f"[quiz-gen] Skipping chunk {chunk.chunk_id}: {e}")
        
        await asyncio.sleep(15)  # 5 second gap = max 12 requests/min, under the 15 limit
    await db.sources.update_one(
        {"source_id": req.source_id},
        {"$set": {"question_count": total_generated}}
    )

    return GenerateQuizResponse(
        source_id=req.source_id,
        questions_generated=total_generated,
        message=f"Generated {total_generated} questions using {llm.provider_name()}",
    )
