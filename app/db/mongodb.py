from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

client: AsyncIOMotorClient = None


async def connect_db():
    global client
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    print(f"Connected to MongoDB at {settings.MONGODB_URL}")
    await create_indexes()


async def disconnect_db():
    global client
    if client:
        client.close()
        print("Disconnected from MongoDB")


def get_db():
    return client[settings.MONGODB_DB]


async def create_indexes():
    db = get_db()
    await db.chunks.create_index([("source_id", 1)])
    await db.chunks.create_index([("topic", 1)])
    await db.questions.create_index([("topic", 1), ("difficulty", 1)])
    await db.questions.create_index([("chunk_id", 1)])
    await db.answers.create_index([("student_id", 1)])
    await db.answers.create_index([("question_id", 1)])
    print("MongoDB indexes created")
