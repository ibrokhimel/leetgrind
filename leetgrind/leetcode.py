import httpx
from .models import Problem

ENDPOINT = "https://leetcode.com/graphql"
_HEADERS = {"Referer": "https://leetcode.com", "User-Agent": "leetgrind/0.1"}

QUESTION_QUERY = """
query questionData($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    questionFrontendId title titleSlug difficulty isPaidOnly content
    topicTags { slug }
    codeSnippets { langSlug code }
  }
}"""

DAILY_QUERY = """
query { activeDailyCodingChallengeQuestion { question { titleSlug } } }"""


class LeetCodeUnavailable(Exception):
    """LeetCode could not be reached or returned something unusable."""


def _post(query: str, variables: dict, client: httpx.Client | None) -> dict:
    owned = client is None
    client = client or httpx.Client(timeout=10.0)
    try:
        resp = client.post(ENDPOINT, json={"query": query, "variables": variables},
                           headers=_HEADERS)
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise LeetCodeUnavailable(str(exc)) from exc
    finally:
        if owned:
            client.close()


def fetch_problem(slug: str, *, client: httpx.Client | None = None) -> Problem:
    payload = _post(QUESTION_QUERY, {"titleSlug": slug}, client)
    try:
        q = (payload.get("data") or {}).get("question")
        if not q:
            raise LeetCodeUnavailable(f"no such problem: {slug}")
        snippets = q.get("codeSnippets") or []
        stub = next((s["code"] for s in snippets if s["langSlug"] == "python3"), None)
        return Problem(
            id=int(q["questionFrontendId"]),
            slug=q["titleSlug"],
            title=q["title"],
            difficulty=q["difficulty"],
            tags=tuple(t["slug"] for t in (q.get("topicTags") or [])),
            is_paid_only=bool(q.get("isPaidOnly")),
            stub=stub,
            content_html=q.get("content"),
        )
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise LeetCodeUnavailable(f"unexpected response shape: {exc}") from exc


def fetch_daily(*, client: httpx.Client | None = None) -> str:
    payload = _post(DAILY_QUERY, {}, client)
    try:
        return payload["data"]["activeDailyCodingChallengeQuestion"]["question"]["titleSlug"]
    except (KeyError, TypeError) as exc:
        raise LeetCodeUnavailable(f"unexpected daily response: {exc}") from exc
