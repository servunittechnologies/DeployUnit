"""Lightweight log line parser — derives a severity from a single line of text.

Used both by the live log stream (deployments/stream) and by sync_deployments
when it stores parsed logs on a deployment row, so the frontend can filter.
"""
import re
from typing import Literal

Severity = Literal["error", "warning", "info", "build", "deploy", "debug"]

# Strip ANSI colour codes
_ANSI = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
_TS_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[\.\dZ:+-]*\s+")
_BRACKET_TAG = re.compile(r"^\[([A-Z]{3,8})\]\s*")


def parse_log_line(raw: str) -> dict:
    line = _ANSI.sub("", raw or "").rstrip("\n").rstrip("\r")
    text = line
    text = _TS_PREFIX.sub("", text).strip()
    low = text.lower()

    severity: Severity = "info"

    # Bracket-tagged lines we emit ourselves
    m = _BRACKET_TAG.match(text)
    if m:
        tag = m.group(1).upper()
        if tag in ("ERROR", "FAIL", "FATAL"):
            severity = "error"
        elif tag in ("WARN", "WARNING"):
            severity = "warning"
        elif tag in ("BUILD",):
            severity = "build"
        elif tag in ("DEPLOY", "QUEUE", "STATUS"):
            severity = "deploy"
        else:
            severity = "info"
    else:
        if any(k in low for k in (
            "error", "fatal", "failed", "failure", "panic", "traceback",
            "exit code 1", "exit code 128", "cannot find", "could not", "✘", "✗",
        )):
            severity = "error"
        elif any(k in low for k in (
            "warning", "warn:", "deprecated", "deprecation", "⚠", "skipping",
        )):
            severity = "warning"
        elif any(k in low for k in (
            "compiling", "building", "yarn install", "yarn build",
            "npm install", "pnpm install", "bun install", "installing",
            "nixpacks", "docker build", "compiled", "step ",
        )):
            severity = "build"
        elif any(k in low for k in (
            "deploying", "deployed", "rolling out", "starting", "started",
            "container", "healthcheck", "health check",
        )):
            severity = "deploy"

    return {"text": line, "severity": severity}


def parse_log_lines(lines: list[str]) -> list[dict]:
    return [parse_log_line(ln) for ln in lines if ln]


_FAIL_BLOCK = re.compile(r"(?:^|\n)([^\n]*(?:fatal|failed|error)[^\n]*)", re.I)


# Errors that are NOT the user's fault — typically Docker/Coolify race conditions
# during cleanup. Surface a clearer message AND signal that a retry is safe.
_TRANSIENT_PATTERNS = [
    re.compile(r"No such container:\s*([a-zA-Z0-9]+)"),
    re.compile(r"network .+ not found", re.I),
    re.compile(r"failed to remove network", re.I),
    re.compile(r"context canceled", re.I),
    re.compile(r"connection refused.*coolify", re.I),
]


def classify_failure(lines: list[str]) -> dict:
    """Return {summary: str | None, transient: bool}.

    `transient=True` means the failure is a known build-engine race condition
    and the caller should consider auto-retrying instead of surfacing as an
    error to the user.
    """
    if not lines:
        return {"summary": None, "transient": False}
    joined = "\n".join(lines[-150:])

    for pat in _TRANSIENT_PATTERNS:
        if pat.search(joined):
            return {
                "summary": (
                    "Build-engine glitch (transient container/network error). "
                    "Auto-retrying — no action needed."
                ),
                "transient": True,
            }

    return {"summary": extract_failure_summary(lines), "transient": False}


def extract_failure_summary(lines: list[str]) -> str | None:
    """Return the most useful failure message from a build log."""
    if not lines:
        return None
    joined = "\n".join(lines[-150:])
    # Common Coolify errors first
    m = re.search(r"Remote branch ([\w./-]+) not found", joined)
    if m:
        branch = m.group(1)
        return (
            f"Git clone failed: branch '{branch}' does not exist on the remote. "
            f"Open Settings → Default branch and pick the actual default branch (e.g. 'main', 'master', or 'canary')."
        )
    m = re.search(r"Authentication failed for ['\"]?(https?://[^\s'\"]+)", joined)
    if m:
        return f"Git clone failed: authentication required for {m.group(1)}. Connect GitHub on Settings to deploy private repos."
    m = re.search(r"exit code (\d+)", joined)
    if m:
        # Bubble up the most relevant failure-looking line
        candidates = [ln for ln in lines[-100:] if any(k in ln.lower() for k in ("fatal", "error", "failed"))]
        if candidates:
            return candidates[0].strip()[:240]
        return f"Build exited with code {m.group(1)}. Check the log above for details."
    return None
