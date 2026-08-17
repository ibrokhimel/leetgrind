import pytest
from leetgrind.urls import parse_slug

@pytest.mark.parametrize("text,expected", [
    ("https://leetcode.com/problems/two-sum/", "two-sum"),
    ("https://leetcode.com/problems/two-sum", "two-sum"),
    ("http://leetcode.com/problems/trapping-rain-water/description/", "trapping-rain-water"),
    ("https://leetcode.com/problems/two-sum/?envType=daily-question&envId=2026-08-17", "two-sum"),
    ("https://leetcode.cn/problems/two-sum/", "two-sum"),
    ("leetcode.com/problems/two-sum/", "two-sum"),
    ("  https://leetcode.com/problems/two-sum/  ", "two-sum"),
    ("two-sum", "two-sum"),
    ("Two Sum", "two-sum"),
])
def test_parse_slug(text, expected):
    assert parse_slug(text) == expected

@pytest.mark.parametrize("bad", ["", "   ", "https://example.com/", "https://leetcode.com/contest/x/"])
def test_parse_slug_rejects(bad):
    with pytest.raises(ValueError):
        parse_slug(bad)
