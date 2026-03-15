from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.db.mongodb import connect_db, disconnect_db
from app.api import ingest, quiz, answers, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await disconnect_db()


app = FastAPI(
    title="Peblo Quiz Engine",
    description="AI-powered content ingestion and adaptive quiz platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(ingest.router, prefix="/api", tags=["ingestion"])
app.include_router(quiz.router, prefix="/api", tags=["quiz"])
app.include_router(answers.router, prefix="/api", tags=["answers"])


@app.get("/")
async def root():
    return {
        "service": "Peblo Quiz Engine",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
