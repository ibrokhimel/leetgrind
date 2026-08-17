from leetgrind.examples import extract_examples, Example
from leetgrind.models import Problem

def make(html, title="Two Sum", tags=("array",)):
    return Problem(id=1, slug="two-sum", title=title, difficulty="Easy",
                   tags=tags, is_paid_only=False, stub="class Solution: pass",
                   content_html=html)

STANDARD = """
<p><strong>Example 1:</strong></p>
<pre><strong>Input:</strong> nums = [2,7,11,15], target = 9
<strong>Output:</strong> [0,1]</pre>
<p><strong>Example 2:</strong></p>
<pre><strong>Input:</strong> nums = [3,2,4], target = 6
<strong>Output:</strong> [1,2]</pre>"""

def test_extracts_standard_examples():
    got = extract_examples(make(STANDARD))
    assert got == (Example(args=("[2,7,11,15]", "9"), expected="[0,1]"),
                   Example(args=("[3,2,4]", "6"), expected="[1,2]"))

def test_returns_empty_when_no_content():
    assert extract_examples(make(None)) == ()

def test_returns_empty_for_design_problems():
    html = """<pre><strong>Input:</strong>
["LRUCache","put","get"]
[[2],[1,1],[1]]
<strong>Output:</strong>
[null,null,1]</pre>"""
    assert extract_examples(make(html, title="LRU Cache", tags=("design",))) == ()

def test_returns_empty_for_in_place_problems():
    html = """<pre><strong>Input:</strong> nums = [1,1,2]
<strong>Output:</strong> 2, nums = [1,2,_]</pre>"""
    assert extract_examples(make(html, title="Remove Duplicates")) == ()

def test_returns_empty_when_any_answer_accepted():
    html = """<pre><strong>Input:</strong> nums = [1,2,3]
<strong>Output:</strong> [1,2,3]</pre>
<p><strong>Note:</strong> You may return the answer in <em>any order</em>.</p>"""
    assert extract_examples(make(html)) == ()

def test_returns_empty_on_unparseable_literals():
    html = """<pre><strong>Input:</strong> root = [1,null,2,3]
<strong>Output:</strong> &lt;some tree&gt;</pre>"""
    assert extract_examples(make(html)) == ()
