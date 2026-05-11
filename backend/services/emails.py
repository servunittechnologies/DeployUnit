"""DeployHub transactional email service.

Top-level senders for the 3 system flows:
  * send_welcome(user)
  * send_password_reset_admin(user, new_password)   — admin set a new pw
  * send_password_reset_link(user, reset_url)       — user clicked "forgot pw"
  * send_notification(user, event_type, title, body, extras)

Each sender:
  - Renders a branded HTML + text email
  - Calls clients.mailersend.send
  - Writes a row to db.notification_sends so the user can audit

Failures degrade gracefully: if MailerSend isn't configured, the send is
logged as `status=skipped` and the calling code keeps working.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from clients import mailersend
from db import get_db

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _frontend_url() -> str:
    return (os.environ.get("FRONTEND_URL") or "").rstrip("/")


# ─────────────────────── shared HTML chrome ───────────────────────
_BASE_CSS = """
  body { margin:0; padding:0; background:#0a0a0a; color:#e8e8e8; font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; }
  .wrap { max-width:560px; margin:0 auto; padding:32px 20px; }
  .card { background:#101010; border:1px solid #1f1f1f; padding:32px; }
  h1 { font-size:24px; letter-spacing:-0.02em; margin:0 0 16px; color:#fff; font-weight:600; }
  p { font-size:15px; line-height:1.55; margin:0 0 14px; color:#c8c8c8; }
  .btn { display:inline-block; padding:12px 22px; background:#00d9ff; color:#000 !important; font-weight:600; text-decoration:none; font-size:14px; margin:6px 0; }
  .meta { font-size:11px; color:#666; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; margin-top:18px; }
  .accent { color:#00d9ff; }
  .alert-red { border-left:3px solid #ef4444; padding-left:14px; }
  .alert-green { border-left:3px solid #22c55e; padding-left:14px; }
  .alert-amber { border-left:3px solid #f59e0b; padding-left:14px; }
  .footer { font-size:11px; color:#555; text-align:center; padding:20px; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }
  a { color:#00d9ff; }
"""


def _shell(title: str, body: str) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{title}</title><style>{_BASE_CSS}</style></head>
<body><div class="wrap"><div class="card">{body}</div>
<div class="footer">DeployHub · Hosting for Next.js &amp; Node<br>This is a transactional email.</div></div></body></html>"""


# ─────────────────────── shared persistence helper ───────────────────────
async def _log_email(*, user_id: Optional[str], workspace_id: Optional[str],
                     to: str, subject: str, event_type: str, result: dict) -> None:
    """Record this email send in db.notification_sends for the audit UI."""
    import uuid as _uuid
    await get_db().notification_sends.insert_one({
        "id": _uuid.uuid4().hex,
        "user_id": user_id,
        "workspace_id": workspace_id,
        "channel": "email",
        "event_type": event_type,
        "to": to,
        "subject": subject,
        "status": "sent" if result.get("ok") else ("skipped" if result.get("status") == "not_configured" else "failed"),
        "cost": 0,
        "message_id": result.get("message_id"),
        "error": result.get("error"),
        "created_at": _now_iso(),
    })


# ─────────────────────── 1. Welcome ───────────────────────
async def send_welcome(user: dict) -> dict:
    """Sent the moment a user registers. Non-blocking — call from a BackgroundTask."""
    if not user or not user.get("email"):
        return {"ok": False, "status": "bad_user"}
    base = _frontend_url() or "https://deployhub.app"
    name = user.get("name") or user["email"].split("@")[0]
    html = _shell("Welcome to DeployHub", f"""
      <h1>Welcome aboard, {name}.</h1>
      <p>Your account is live. You can start deploying Next.js or Node apps from a GitHub repo in under 60 seconds.</p>
      <p><a class="btn" href="{base}/app">Open the dashboard →</a></p>
      <p class="meta">Things to do next:</p>
      <ul style="font-size:13px;color:#a0a0a0;line-height:1.7;">
        <li>Connect GitHub in <a href="{base}/app/settings">Settings → Connected accounts</a></li>
        <li>Hit <span class="accent">+ New App</span> and pick a repo</li>
        <li>Add a custom domain or use the free <span class="accent">{{slug}}.deployhub.app</span></li>
      </ul>
      <p class="meta">If you didn't sign up for DeployHub, ignore this email or reply to let us know.</p>
    """)
    text = f"Welcome to DeployHub, {name}.\n\nYour account is live. Open the dashboard: {base}/app\n\nIf this wasn't you, ignore this email."
    res = await mailersend.send(
        to_email=user["email"], to_name=name,
        subject="Welcome to DeployHub",
        html=html, text=text, tags=["welcome"],
    )
    await _log_email(user_id=user.get("id"), workspace_id=None,
                     to=user["email"], subject="Welcome to DeployHub",
                     event_type="welcome", result=res)
    return res


# ─────────────────────── 2a. Password reset (admin set new pw) ───────────────────────
async def send_password_reset_admin(user: dict, new_password: str, actor_email: Optional[str] = None) -> dict:
    """Sent when an admin sets a new password for a user via the admin UI.
    We email the user the new credentials with a strong nudge to change it."""
    if not user or not user.get("email"):
        return {"ok": False, "status": "bad_user"}
    base = _frontend_url() or "https://deployhub.app"
    name = user.get("name") or user["email"].split("@")[0]
    html = _shell("Your password was reset", f"""
      <h1>Your password was reset by an administrator.</h1>
      <p>A DeployHub admin{f' ({actor_email})' if actor_email else ''} set a new password for your account.</p>
      <div class="alert-amber"><p><strong>Your temporary password:</strong></p>
        <p style="font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:15px; background:#000; padding:12px; border:1px solid #1f1f1f;">{new_password}</p>
      </div>
      <p><a class="btn" href="{base}/login">Sign in now →</a></p>
      <p>For your safety, change this password immediately under <a href="{base}/app/settings">Settings → Change password</a>.</p>
      <p class="meta">Didn't expect this? Contact support immediately.</p>
    """)
    text = (f"Your DeployHub password was reset by an admin{f' ({actor_email})' if actor_email else ''}.\n\n"
            f"Temporary password: {new_password}\n\nSign in: {base}/login\nChange it immediately under Settings → Change password.")
    res = await mailersend.send(
        to_email=user["email"], to_name=name,
        subject="Your DeployHub password was reset",
        html=html, text=text, tags=["password_reset", "admin"],
    )
    await _log_email(user_id=user.get("id"), workspace_id=None,
                     to=user["email"], subject="Your DeployHub password was reset",
                     event_type="password_reset_admin", result=res)
    return res


# ─────────────────────── 2b. Forgot-password link ───────────────────────
async def send_password_reset_link(user: dict, reset_url: str, expires_minutes: int = 60) -> dict:
    """Sent when a user clicks 'Forgot password' and we issue a one-time link."""
    if not user or not user.get("email"):
        return {"ok": False, "status": "bad_user"}
    name = user.get("name") or user["email"].split("@")[0]
    html = _shell("Reset your password", f"""
      <h1>Reset your DeployHub password.</h1>
      <p>Hi {name}, we got a request to reset the password on your DeployHub account.</p>
      <p><a class="btn" href="{reset_url}">Reset password →</a></p>
      <p class="meta">This link expires in {expires_minutes} minutes.<br>
        If the button doesn't work, copy this URL:<br>
        <span class="accent">{reset_url}</span></p>
      <p class="meta">Didn't request this? You can safely ignore the email — your password won't change.</p>
    """)
    text = f"Reset your DeployHub password.\n\n{reset_url}\n\nExpires in {expires_minutes} minutes. If this wasn't you, ignore this email."
    res = await mailersend.send(
        to_email=user["email"], to_name=name,
        subject="Reset your DeployHub password",
        html=html, text=text, tags=["password_reset", "self_serve"],
    )
    await _log_email(user_id=user.get("id"), workspace_id=None,
                     to=user["email"], subject="Reset your DeployHub password",
                     event_type="password_reset_link", result=res)
    return res


# ─────────────────────── 3. Notification alerts ───────────────────────
_NOTIFICATION_PALETTE = {
    "deploy_failed":    ("alert-red",   "🔴"),
    "deploy_succeeded": ("alert-green", "🟢"),
    "app_down":         ("alert-red",   "🔴"),
    "app_recovered":    ("alert-green", "🟢"),
    "build_warning":    ("alert-amber", "🟠"),
    "domain_expiring":  ("alert-amber", "🟠"),
    "credits_low":      ("alert-amber", "🟠"),
}


async def send_notification(*, user: dict, workspace_id: Optional[str], event_type: str,
                            title: str, body: str, extras: Optional[dict] = None) -> dict:
    """Notification alert email. Called by services/notifications_sms.py when
    the user has email enabled for `event_type`."""
    if not user or not user.get("email"):
        return {"ok": False, "status": "bad_user"}
    base = _frontend_url() or "https://deployhub.app"
    css_class, _emoji = _NOTIFICATION_PALETTE.get(event_type, ("alert-amber", "🔔"))
    extra_html = ""
    if extras:
        rows = "".join(
            f'<tr><td style="padding:4px 10px 4px 0; color:#888;">{k}</td><td style="padding:4px 0; color:#ccc;">{v}</td></tr>'
            for k, v in extras.items()
        )
        extra_html = f'<table style="margin-top:14px; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px;">{rows}</table>'
    html = _shell(title, f"""
      <h1>{title}</h1>
      <div class="{css_class}">
        <p>{body}</p>
        {extra_html}
      </div>
      <p><a class="btn" href="{base}/app">Open dashboard →</a></p>
      <p class="meta">Event: <span class="accent">{event_type}</span></p>
      <p class="meta">You're receiving this because you enabled email for this event.<br>
        Manage in <a href="{base}/app/settings">Settings → Notification preferences</a>.</p>
    """)
    text = f"{title}\n\n{body}\n\nEvent: {event_type}\nOpen: {base}/app\n\nManage preferences in Settings → Notification preferences."
    res = await mailersend.send(
        to_email=user["email"], to_name=user.get("name"),
        subject=f"[DeployHub] {title}",
        html=html, text=text, tags=["notification", event_type],
    )
    await _log_email(user_id=user.get("id"), workspace_id=workspace_id,
                     to=user["email"], subject=f"[DeployHub] {title}",
                     event_type=event_type, result=res)
    return res
