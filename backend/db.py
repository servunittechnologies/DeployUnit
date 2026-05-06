"""MongoDB connection singleton."""
import os
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def connect():
    global _client, _db
    if _client is None:
        _client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        _db = _client[os.environ["DB_NAME"]]
    return _db


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        return connect()
    return _db


async def disconnect():
    global _client, _db
    if _client is not None:
        _client.close()
        _client = None
        _db = None


async def ensure_indexes():
    db = get_db()
    await db.users.create_index("email", unique=True)
    await db.workspaces.create_index("slug", unique=True)
    await db.workspace_members.create_index([("workspace_id", 1), ("user_id", 1)], unique=True)
    await db.apps.create_index([("workspace_id", 1), ("slug", 1)], unique=True)
    await db.deployments.create_index("app_id")
    await db.deployments.create_index("started_at")
    await db.domains.create_index("domain", unique=True)
    await db.monitoring_results.create_index([("app_id", 1), ("timestamp", -1)])
    await db.notifications.create_index([("workspace_id", 1), ("created_at", -1)])
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.login_attempts.create_index("identifier")
    await db.invoices_cache.create_index("workspace_id")
