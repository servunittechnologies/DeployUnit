"""Admin / demo seeding."""
import os
import logging
from datetime import datetime, timezone
from slugify import slugify
import uuid
from db import get_db
from auth_utils import hash_password, verify_password

logger = logging.getLogger(__name__)


async def _ensure_user(email: str, password: str, name: str, role: str) -> dict:
    db = get_db()
    existing = await db.users.find_one({"email": email})
    if existing is None:
        doc = {
            "id": str(uuid.uuid4()),
            "email": email,
            "password_hash": hash_password(password),
            "name": name,
            "role": role,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(doc)
        return doc
    if not verify_password(password, existing["password_hash"]):
        await db.users.update_one(
            {"email": email}, {"$set": {"password_hash": hash_password(password)}}
        )
    return existing


async def _ensure_workspace(owner_id: str, name: str, ws_type: str = "solo") -> dict:
    db = get_db()
    slug = slugify(f"{name}-{owner_id[:6]}")
    ws = await db.workspaces.find_one({"slug": slug})
    if ws:
        return ws
    doc = {
        "id": str(uuid.uuid4()),
        "name": name,
        "slug": slug,
        "type": ws_type,
        "owner_id": owner_id,
        "plan": "free",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.workspaces.insert_one(doc)
    await db.workspace_members.insert_one(
        {
            "id": str(uuid.uuid4()),
            "workspace_id": doc["id"],
            "user_id": owner_id,
            "role": "owner",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return doc


async def seed_initial_data():
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@deployhub.dev")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    demo_email = os.environ.get("DEMO_EMAIL", "demo@deployhub.dev")
    demo_password = os.environ.get("DEMO_PASSWORD", "demo1234")

    admin = await _ensure_user(admin_email, admin_password, "Platform Admin", "admin")
    demo = await _ensure_user(demo_email, demo_password, "Demo Founder", "user")

    await _ensure_workspace(admin["id"], "Platform HQ", "agency")
    demo_ws = await _ensure_workspace(demo["id"], "Acme Studio", "agency")

    db = get_db()
    # Seed a sample project + apps for the demo workspace so the dashboard is alive.
    proj_count = await db.projects.count_documents({"workspace_id": demo_ws["id"]})
    if proj_count == 0:
        proj = {
            "id": str(uuid.uuid4()),
            "workspace_id": demo_ws["id"],
            "name": "Client: NovaBrew Coffee",
            "slug": "novabrew",
            "description": "Marketing site + dashboard for NovaBrew",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.projects.insert_one(proj)

        sample_apps = [
            {
                "name": "novabrew-web",
                "framework": "nextjs",
                "repo_url": "https://github.com/novabrew/web.git",
                "status": "live",
                "primary_url": "https://novabrew.example.com",
            },
            {
                "name": "novabrew-api",
                "framework": "node",
                "repo_url": "https://github.com/novabrew/api.git",
                "status": "building",
                "primary_url": "https://api.novabrew.example.com",
            },
            {
                "name": "novabrew-admin",
                "framework": "nextjs",
                "repo_url": "https://github.com/novabrew/admin.git",
                "status": "failed",
                "primary_url": None,
            },
        ]
        for app in sample_apps:
            app_id = str(uuid.uuid4())
            await db.apps.insert_one(
                {
                    "id": app_id,
                    "workspace_id": demo_ws["id"],
                    "project_id": proj["id"],
                    "name": app["name"],
                    "slug": slugify(app["name"]),
                    "framework": app["framework"],
                    "repo_url": app["repo_url"],
                    "branch": "main",
                    "build_command": None,
                    "start_command": None,
                    "env_vars": {"NODE_ENV": "production"},
                    "coolify_app_uuid": None,
                    "status": app["status"],
                    "primary_url": app["primary_url"],
                    "last_deploy_at": datetime.now(timezone.utc).isoformat(),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            # one historical deployment per app
            await db.deployments.insert_one(
                {
                    "id": str(uuid.uuid4()),
                    "app_id": app_id,
                    "workspace_id": demo_ws["id"],
                    "status": app["status"],
                    "commit_sha": uuid.uuid4().hex[:7],
                    "commit_message": "chore: initial deploy",
                    "branch": "main",
                    "logs": [
                        "[BUILD] nixpacks detect: nextjs",
                        "[BUILD] yarn install --frozen-lockfile",
                        "[BUILD] yarn build",
                        f"[STATUS] {app['status']}",
                    ],
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }
            )

    # ensure at least one demo notification
    notif_count = await db.notifications.count_documents({"workspace_id": demo_ws["id"]})
    if notif_count == 0:
        await db.notifications.insert_one(
            {
                "id": str(uuid.uuid4()),
                "workspace_id": demo_ws["id"],
                "user_id": demo["id"],
                "type": "welcome",
                "title": "Welcome to DeployHub",
                "message": "Connect a repo and deploy your first app in 2 clicks.",
                "severity": "info",
                "read": False,
                "link": "/app/apps/new",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    # Persist test creds for testing agent
    try:
        os.makedirs("/app/memory", exist_ok=True)
        with open("/app/memory/test_credentials.md", "w") as f:
            f.write(
                "# DeployHub Test Credentials\n\n"
                f"## Admin\n- Email: {admin_email}\n- Password: {admin_password}\n- Role: admin\n\n"
                f"## Demo user (has seeded workspace + apps)\n- Email: {demo_email}\n- Password: {demo_password}\n- Role: user\n\n"
                "## Auth endpoints\n"
                "- POST /api/auth/register\n"
                "- POST /api/auth/login\n"
                "- POST /api/auth/logout\n"
                "- GET /api/auth/me\n"
            )
    except Exception as e:
        logger.warning("could not write test_credentials: %s", e)

    logger.info("Seed complete: admin=%s demo=%s", admin_email, demo_email)
