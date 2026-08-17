import re

_URL_RE = re.compile(r"leetcode\.(?:com|cn)/problems/([a-z0-9-]+)", re.IGNORECASE)
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def parse_slug(text: str) -> str:
    """Extract a LeetCode problem slug from a URL, bare slug, or plain title."""
    text = text.strip()
    if not text:
        raise ValueError("empty input")

    if match := _URL_RE.search(text):
        return match.group(1).lower()

    if "/" in text or "leetcode." in text.lower():
        raise ValueError(f"not a LeetCode problem URL: {text!r}")

    candidate = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if not candidate or not _SLUG_RE.match(candidate):
        raise ValueError(f"cannot derive a slug from: {text!r}")
    return candidate
