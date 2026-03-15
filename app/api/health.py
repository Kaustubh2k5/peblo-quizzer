from fastapi import APIRouter
from app.db.mongodb import get_db, client
from app.db.redis_client import get_redis
from app.core.config import settings

router = APIRouter()


@router.get("/health")
async def health():
    """Full system health check — MongoDB, Redis, LLM config."""
    status = {"api": "ok", "mongodb": "unknown", "redis": "unknown", "llm_provider": settings.LLM_PROVIDER}

    try:
        await client.admin.command("ping")
        status["mongodb"] = "ok"
    except Exception as e:
        status["mongodb"] = f"error: {e}"

    try:
        redis = await get_redis()
        await redis.ping()
        status["redis"] = "ok"
    except Exception as e:
        status["redis"] = f"error: {e}"

    # Check API key is configured
    key_map = {
        "nvidia": settings.NVIDIA_API_KEY,
        "openai": settings.OPENAI_API_KEY,
        "anthropic": settings.ANTHROPIC_API_KEY,
        "gemini": settings.GEMINI_API_KEY,
    }
    key = key_map.get(settings.LLM_PROVIDER, "")
    status["llm_key_set"] = bool(key and key != "")

    overall = "ok" if all(v == "ok" for k, v in status.items() if k not in ("llm_provider", "llm_key_set")) else "degraded"
    status["overall"] = overall

    return status
