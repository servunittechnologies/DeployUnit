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
    await db.users.create_index("email_ci")
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
    await db.billing_profiles.create_index("workspace_id", unique=True)
    await db.mollie_customers.create_index("workspace_id", unique=True)
    await db.mollie_customers.create_index("mollie_customer_id")
    await db.payments.create_index("mollie_payment_id", unique=True)
    await db.payments.create_index("workspace_id")
    await db.invoices.create_index("invoice_number", unique=True)
    await db.invoices.create_index("workspace_id")
    await db.invoices.create_index("mollie_payment_id")
    await db.webhook_logs.create_index("mollie_payment_id")
    await db.oauth_states.create_index("state", unique=True)
    # Notification dispatcher cooldown — unique per (workspace, event, app)
    # so a back-to-back dispatch can't insert two rows. `app_id` is
    # optional → we treat None as a stable key value (Mongo unique index
    # tolerates Nulls because all our docs always include the field).
    await db.event_cooldowns.create_index(
        [("workspace_id", 1), ("event_type", 1), ("app_id", 1)],
        unique=True,
    )
    await db.notification_sends.create_index([("workspace_id", 1), ("created_at", -1)])
    await db.notification_sends.create_index([("user_id", 1), ("created_at", -1)])
    # Custom-subdomain provisioning index — looking up by app/status is the
    # hot path for the 30s verifier tick.
    await db.custom_subdomain_requests.create_index([("status", 1), ("created_at", 1)])
    await db.custom_subdomain_requests.create_index([("app_id", 1), ("status", 1)])

