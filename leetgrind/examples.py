import ast
import html as html_mod
import re
from dataclasses import dataclass

from .models import Problem

_PRE_RE = re.compile(r"<pre>(.*?)</pre>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_INPUT_RE = re.compile(r"Input:\s*(.*?)\s*Output:\s*(.*?)(?:\s*Explanation:|$)", re.DOTALL)
_ARG_RE = re.compile(r"[A-Za-z_]\w*\s*=\s*")

_UNSUPPORTED_TAGS = {"design"}
_ANY_ORDER_RE = re.compile(r"in any order|any valid|multiple valid", re.IGNORECASE)


@dataclass(frozen=True)
class Example:
    args: tuple[str, ...]
    expected: str


def _strip(fragment: str) -> str:
    return html_mod.unescape(_TAG_RE.sub("", fragment)).strip()


def _is_literal(src: str) -> bool:
    try:
        ast.literal_eval(src)
    except Exception:
        return False
    return True


def _split_args(raw: str) -> tuple[str, ...] | None:
    """Split `nums = [1,2], target = 9` into ('[1,2]', '9')."""
    if not _ARG_RE.match(raw):
        return None
    parts = []
    bounds = [m.start() for m in _ARG_RE.finditer(raw)]
    for start, end in zip(bounds, bounds[1:] + [len(raw)]):
        value = raw[_ARG_RE.match(raw, start).end():end].strip().rstrip(",").strip()
        parts.append(value)
    return tuple(parts) if parts else None


def extract_examples(problem: Problem) -> tuple[Example, ...]:
    """Best-effort example extraction. Returns () whenever it is not confident."""
    html = problem.content_html
    if not html:
        return ()
    if _UNSUPPORTED_TAGS & set(problem.tags):
        return ()
    if _ANY_ORDER_RE.search(_strip(html)):
        return ()

    examples: list[Example] = []
    for block in _PRE_RE.findall(html):
        text = _strip(block)
        match = _INPUT_RE.search(text)
        if not match:
            return ()
        raw_args, raw_out = match.group(1).strip(), match.group(2).strip()
        # In-place problems report the mutated input in the output.
        if "=" in raw_out or "_" in raw_out:
            return ()
        args = _split_args(raw_args)
        if not args or not all(_is_literal(a) for a in args) or not _is_literal(raw_out):
            return ()
        examples.append(Example(args=args, expected=raw_out))
    return tuple(examples)
