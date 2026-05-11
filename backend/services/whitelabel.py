"""Centrale whitelabel-sanitizer voor alles wat naar de eindgebruiker gaat.

De build engine (Coolify) lekt zijn merknaam, helper image hostname,
env-var prefixes en logo overal in de build-output. We willen NIETS van die
strings naar onze UI laten lekken — alles moet eruit zien alsof DeployUnit
de build engine zelf is. Deze module is de single source of truth voor die
substituties.
"""
import re
from typing import Iterable

# Order matters: longer patterns first so 'coolify-helper' doesn't get
# partially rewritten by the bare 'coolify' rule.
_SUBS: list[tuple[re.Pattern, str]] = [
    # Docker helper image (`ghcr.io/coollabsio/coolify-helper:...`)
    (re.compile(r"ghcr\.io/coollabsio/coolify-helper:[\w.-]+", re.IGNORECASE),
     "build-engine-helper:internal"),
    (re.compile(r"ghcr\.io/coollabsio/[\w-]+:[\w.-]+", re.IGNORECASE),
     "build-engine/internal"),
    (re.compile(r"coollabsio/coolify-helper", re.IGNORECASE),
     "build-engine-helper"),
    (re.compile(r"coollabsio", re.IGNORECASE),
     "build-engine"),

    # Environment variables Coolify injects into builds
    (re.compile(r"COOLIFY_URL", re.IGNORECASE),         "BUILD_ENGINE_URL"),
    (re.compile(r"COOLIFY_FQDN", re.IGNORECASE),        "BUILD_ENGINE_FQDN"),
    (re.compile(r"COOLIFY_BRANCH", re.IGNORECASE),      "BUILD_ENGINE_BRANCH"),
    (re.compile(r"COOLIFY_RESOURCE_UUID", re.IGNORECASE), "BUILD_ENGINE_RESOURCE_UUID"),
    (re.compile(r"COOLIFY_CONTAINER_NAME", re.IGNORECASE), "BUILD_ENGINE_CONTAINER_NAME"),
    (re.compile(r"COOLIFY_", re.IGNORECASE),            "BUILD_ENGINE_"),

    # Build runner / hostnames
    (re.compile(r"--add-host coolify(?:-db|-realtime)?:[\d.]+", re.IGNORECASE),
     "--add-host build-engine:internal"),
    (re.compile(r"\bcoolify-(?:db|realtime|proxy)\b", re.IGNORECASE),
     "build-engine-internal"),

    # Bare brand mentions in any casing — last so it doesn't pre-empt the
    # specific rules above
    (re.compile(r"\bcoolify\b", re.IGNORECASE),         "build engine"),
]

# A handful of strings should pass through untouched even when they're
# substrings of the patterns above (e.g. testid attributes, internal DB
# fields). Those are filtered out at the call site, not here.


def sanitize(text: str) -> str:
    """Strip every recognisable build-engine brand marker from a string."""
    if not text:
        return text
    out = text
    for pattern, replacement in _SUBS:
        out = pattern.sub(replacement, out)
    return out


def sanitize_lines(lines: Iterable[str]) -> list[str]:
    return [sanitize(ln) for ln in lines]
