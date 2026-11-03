"""Shared proof-text rules: Lean comment stripping and the forbidden-token check.

Used by the B0 judge (`llm_baseline.judge`, judge version v2) and meant to be shared
with the proof-search backend so both apply the same `sorry`/`admit`/`axiom` rule.

The rule: the proof text is checked after its comments are removed (a token that
only appears in a comment is not part of the proof); Lean's own output is checked
verbatim, because there `declaration uses 'sorry'` is a real warning, never a comment.
"""

import re

FORBIDDEN_RE = re.compile(r"\b(sorry|admit|axiom)\b")
# Pseudo-token reported when a block comment is never closed. Lean rejects the file
# too, but the rest of the text cannot be judged, so the proof fails here.
UNTERMINATED_COMMENT = "unterminated_comment"
# Constructs the comment stripper does not model; see find_forbidden_in_proof.
_UNPARSED_RE = re.compile(r"!\"|'\\?\"'")

# A Lean character literal: 'a', '\n', '\'', '\x41', 'ሴ'. Only matched where a
# `'` cannot be the prime of an identifier (see `_prev_is_ident`).
# Start of a raw string literal: r"..." or r#"..."# (any number of '#', no escapes).
_RAW_STRING_START_RE = re.compile(r'r(#*)"')
_CHAR_LITERAL_RE = re.compile(r"'(?:\\x[0-9a-fA-F]{2}|\\u[0-9a-fA-F]{4}|\\.|[^\\'\n])'")


def _prev_is_ident(text: str, index: int) -> bool:
    if index == 0:
        return False
    prev = text[index - 1]
    return prev.isalnum() or prev in "_'!?"


def strip_lean_comments(text: str) -> tuple[str, bool]:
    """Remove Lean comments -> (stripped_text, unterminated).

    Handles `--` line comments and nested `/- ... -/` block comments (doc comments
    `/-- ... -/` are block comments). Comment symbols inside string literals
    `"..."` (with `\\` escapes), raw strings `r"..."` / `r#"..."#`, `«...»`
    identifiers and character literals are opaque: no comment is looked for in
    them and they are kept verbatim. A raw string or `«` that is never closed is
    kept to the end of the text (conservative: nothing after it is stripped). Inside a block comment, strings are
    not special, as in Lean itself.

    Each comment is replaced by one space and its newlines are kept, so the
    tokens around a comment stay separate (`sor/- -/ry` is not `sorry`) and
    line numbers do not move. `unterminated` is True when a block comment is
    still open at the end of the text; the comment is then stripped to the end.
    An unterminated string is kept to the end of the text.
    """
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n)
            out.append(text[i:j])
            i = j
        elif ch == "r" and not _prev_is_ident(text, i) and _RAW_STRING_START_RE.match(text, i):
            hashes = _RAW_STRING_START_RE.match(text, i).group(1)
            end = text.find('"' + hashes, i + 2 + len(hashes))
            j = n if end < 0 else end + 1 + len(hashes)
            out.append(text[i:j])
            i = j
        elif ch == "«":
            end = text.find("»", i + 1)
            j = n if end < 0 else end + 1
            out.append(text[i:j])
            i = j
        elif ch == "'" and not _prev_is_ident(text, i):
            found = _CHAR_LITERAL_RE.match(text, i)
            if found:
                out.append(found.group(0))
                i = found.end()
            else:
                out.append(ch)
                i += 1
        elif text.startswith("--", i):
            j = text.find("\n", i)
            out.append(" ")
            i = n if j < 0 else j  # keep the newline itself
        elif text.startswith("/-", i):
            depth = 1
            j = i + 2
            newlines = 0
            while j < n and depth > 0:
                if text.startswith("/-", j):
                    depth += 1
                    j += 2
                elif text.startswith("-/", j):
                    depth -= 1
                    j += 2
                else:
                    if text[j] == "\n":
                        newlines += 1
                    j += 1
            out.append(" " + "\n" * newlines)
            i = j
            if depth > 0:
                return "".join(out), True
        else:
            out.append(ch)
            i += 1
    return "".join(out), False


def find_forbidden(text: str) -> str | None:
    """First forbidden token in `text` as is (used for Lean output), else None."""
    found = FORBIDDEN_RE.search(text)
    return found.group(1) if found else None


def find_forbidden_in_proof(proof: str) -> str | None:
    """First forbidden token in proof text, ignoring comments, else None.

    An unterminated block comment counts as forbidden (UNTERMINATED_COMMENT).

    Interpolated strings (`s!"..{..}.."`, `m!`, `f!`) may nest string and char
    literals inside `{}`, which the stripper does not parse; a `'"'` char literal
    is the other construct that can desynchronise it. When either appears, the
    raw text is checked instead (the v1 rule): stricter, never looser.
    """
    if _UNPARSED_RE.search(proof):
        return find_forbidden(proof)
    stripped, unterminated = strip_lean_comments(proof)
    token = find_forbidden(stripped)
    if token is None and unterminated:
        return UNTERMINATED_COMMENT
    return token
