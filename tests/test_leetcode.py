import json
from pathlib import Path
import httpx, pytest, respx
from leetgrind.leetcode import fetch_problem, fetch_daily, LeetCodeUnavailable

FIXTURE = json.loads((Path(__file__).parent / "fixtures/two-sum.json").read_text())

@respx.mock
def test_fetch_problem_parses_metadata():
    respx.post("https://leetcode.com/graphql").mock(return_value=httpx.Response(200, json=FIXTURE))
    p = fetch_problem("two-sum")
    assert p.id == 1
    assert p.title == "Two Sum"
    assert p.difficulty == "Easy"
    assert p.tags == ("array", "hash-table")
    assert p.is_paid_only is False
    assert "def twoSum" in p.stub

@respx.mock
def test_fetch_problem_raises_on_http_error():
    respx.post("https://leetcode.com/graphql").mock(return_value=httpx.Response(429))
    with pytest.raises(LeetCodeUnavailable):
        fetch_problem("two-sum")

@respx.mock
def test_fetch_problem_raises_on_unknown_slug():
    respx.post("https://leetcode.com/graphql").mock(
        return_value=httpx.Response(200, json={"data": {"question": None}}))
    with pytest.raises(LeetCodeUnavailable):
        fetch_problem("nope")

@respx.mock
def test_fetch_problem_raises_on_shape_change():
    respx.post("https://leetcode.com/graphql").mock(
        return_value=httpx.Response(200, json={"data": {"question": {"title": "x"}}}))
    with pytest.raises(LeetCodeUnavailable):
        fetch_problem("two-sum")

@respx.mock
def test_fetch_daily_returns_slug():
    respx.post("https://leetcode.com/graphql").mock(return_value=httpx.Response(200, json={
        "data": {"activeDailyCodingChallengeQuestion": {"question": {"titleSlug": "trapping-rain-water"}}}}))
    assert fetch_daily() == "trapping-rain-water"

@respx.mock
def test_paid_only_problem_has_no_stub():
    payload = json.loads(json.dumps(FIXTURE))
    payload["data"]["question"]["isPaidOnly"] = True
    payload["data"]["question"]["content"] = None
    payload["data"]["question"]["codeSnippets"] = None
    respx.post("https://leetcode.com/graphql").mock(return_value=httpx.Response(200, json=payload))
    p = fetch_problem("two-sum")
    assert p.is_paid_only is True
    assert p.stub is None
    assert p.content_html is None
