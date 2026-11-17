"""Split policy text into retrieval chunks that follow the document's own structure.

Why not fixed-size windows: a policy is made of numbered clauses, and a clause is the
unit people cite and the unit a validator must judge. Cutting mid-clause loses meaning,
and cutting across clauses mixes unrelated rules. (On our evaluation set, one chunk per
clause kept 100% of correct answers above the relevance floor, against 84% for
1200-character windows.)

Rules, in order:
1. Repeated page headers/footers and bare page numbers are removed first.
2. Headings become the `section` label and are prefixed to every chunk below them.
3. A numbered clause (`2.1 ...`) is one chunk; wrapped lines are joined to it.
4. Plain prose is packed into chunks of up to TARGET_CHARS, never across a heading.
5. A piece longer than MAX_CHARS is split on sentence boundaries.
6. Nothing is dropped: an uncertain heading that has no body is kept as text.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, replace

from services.policy_text import SourcePage

TARGET_CHARS = 900  # prose is packed up to this size
MAX_CHARS = 1200  # nothing longer is emitted; stays far below the embedding input limit
MIN_CLAUSE_CHARS = 40  # a shorter clause is merged into the next piece of the same section
MAX_HEADING_CHARS = 80
EDGE_LINES = 2  # header/footer candidates: this many lines at the top and bottom of a page

_PAGE_NUMBER = re.compile(r"^(page\s+)?\d+(\s*(of|/)\s*\d+)?$", re.IGNORECASE)
_MARKDOWN_HEADING = re.compile(r"^#{1,6}\s+(.+)$")
_WORD_HEADING = re.compile(r"^(section|article|clause|chapter|part|annex(ure)?|schedule)\s+[a-z0-9]{1,4}\b", re.IGNORECASE)
_NUMBERED_TOP_LEVEL = re.compile(r"^\d+[.)]?\s+\S")  # "2. Casual Leave" - never "2.1 ..."
_NUMBERED_CLAUSE = re.compile(r"^(\d+(\.\d+)+|\d+[.)])\s+\S")  # "2.1 ..." or "3. ..."
_LIST_ITEM = re.compile(r"^([-•*]|\(?[^\W_]{1,3}[.)])\s+\S")  # "- x", "(a) x", "a. x"
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_TERMINAL_PUNCTUATION = (".", "!", "?", ";", ":", ",")
_SENTENCE_ENDINGS = (".", "!", "?")


@dataclass(frozen=True)
class ChunkDraft:
    content: str  # section label + text, exactly what is embedded and later quoted as evidence
    page_number: int | None
    section: str | None


@dataclass
class _Unit:
    section: str | None
    page: int | None
    kind: str  # "clause" or "prose"
    text: str


def chunk_policy(pages: list[SourcePage]) -> list[ChunkDraft]:
    """Turn extracted pages into ordered, de-duplicated chunks."""
    return _dedupe(_pack(_build_units(_to_lines(pages))))


def chunk_text(text: str) -> list[ChunkDraft]:
    """Chunk plain text that has no page information (text-entered policies)."""
    return chunk_policy([SourcePage(None, text)])


# --- step 1: lines, with page furniture removed -------------------------------------------
def _to_lines(pages: list[SourcePage]) -> list[tuple[int | None, str]]:
    repeated = _repeated_furniture(pages)
    lines: list[tuple[int | None, str]] = []
    for page in pages:
        raw = page.text.split("\n")
        edges = _edge_indexes(raw)
        for index, line in enumerate(raw):
            line = line.strip()
            if index in edges and _is_furniture(line, page, repeated):
                continue
            lines.append((page.number, line))
    return lines


def _edge_indexes(raw_lines: list[str]) -> set[int]:
    """Positions of the first and last EDGE_LINES non-empty lines: where headers and footers live."""
    filled = [index for index, line in enumerate(raw_lines) if line.strip()]
    return set(filled[:EDGE_LINES]) | set(filled[-EDGE_LINES:])


def _is_furniture(line: str, page: SourcePage, repeated: set[str]) -> bool:
    if not line:
        return False
    is_page_number = page.number is not None and _PAGE_NUMBER.match(line) is not None
    return is_page_number or _furniture_key(line, page.number) in repeated


def _furniture_key(line: str, page_number: int | None) -> str:
    """Compare lines across pages after masking the page's own number ("Page 3" -> "page #").

    Only that exact token is masked, so "Clause 3.30" on page 3 stays different from
    "Clause 1.30" on page 1 and is never mistaken for a repeating footer.
    """
    key = line.casefold()
    if page_number is not None:
        key = re.sub(rf"(?<![\d.]){page_number}(?![\d.])", "#", key)
    return key


def _repeated_furniture(pages: list[SourcePage]) -> set[str]:
    """Short edge lines that repeat on most pages are headers/footers, not policy content.

    Only the first and last lines of a page are considered: body lines such as
    "Clause 1.1: ...", "Clause 2.1: ..." look alike once numbers are masked, but they are content.
    """
    if len(pages) < 3:
        return set()
    seen: Counter[str] = Counter()
    for page in pages:
        raw = page.text.split("\n")
        edge_lines = {raw[index].strip() for index in _edge_indexes(raw)}
        keys = {_furniture_key(line, page.number) for line in edge_lines if 0 < len(line) <= MAX_HEADING_CHARS}
        seen.update(keys)
    needed = max(3, math.ceil(0.6 * len(pages)))
    return {key for key, count in seen.items() if count >= needed}


# --- step 2: structure -> units -----------------------------------------------------------
def _heading(line: str) -> tuple[str, bool] | None:
    """Return (heading text, is_explicit) when the line is a heading, else None.

    Explicit headings (Markdown/DOCX styles) are certain. Inferred ones (numbered titles,
    "Section 4", ALL CAPS) are guesses, so their text is kept if no body follows.
    """
    if match := _MARKDOWN_HEADING.match(line):
        return match.group(1).strip(), True
    if len(line) > MAX_HEADING_CHARS or line.endswith(_TERMINAL_PUNCTUATION):
        return None
    is_short_numbered_title = _NUMBERED_TOP_LEVEL.match(line) and len(line.split()) <= 10
    if _WORD_HEADING.match(line) or is_short_numbered_title:
        return line, False
    has_letters = sum(char.isalpha() for char in line) >= 3
    if has_letters and line.isupper() and len(line) <= 60:
        return line, False
    return None


class _UnitBuilder:
    """Feeds lines in, collects clause/prose units out, and tracks the current section."""

    def __init__(self) -> None:
        self.units: list[_Unit] = []
        self._section: str | None = None
        self._current: _Unit | None = None
        self._sentence_complete = False
        # An inferred heading seen but not yet followed by body text: (text, page, section before it).
        self._unconfirmed: tuple[str, int | None, str | None] | None = None

    def add(self, page: int | None, line: str) -> None:
        if not line:
            self._close()
        elif (heading := _heading(line)) is not None:
            self._add_heading(page, *heading)
        else:
            self._add_body(page, line)

    def finish(self) -> list[_Unit]:
        self._close()
        self._keep_unconfirmed_heading()
        return self.units

    def _add_heading(self, page: int | None, text: str, explicit: bool) -> None:
        self._close()
        self._keep_unconfirmed_heading()
        self._unconfirmed = None if explicit else (text, page, self._section)
        self._section = text

    def _add_body(self, page: int | None, line: str) -> None:
        self._unconfirmed = None  # body text follows, so the heading guess was right
        if _NUMBERED_CLAUSE.match(line):
            self._start(page, "clause", line)
        elif self._extends_current(line):
            separator = "\n" if _LIST_ITEM.match(line) else " "  # list items stay on their own lines
            self._current.text += separator + line
        else:
            self._start(page, "prose", line)
        self._sentence_complete = line.endswith(_SENTENCE_ENDINGS)

    def _extends_current(self, line: str) -> bool:
        """A wrapped line continues the current unit, unless a finished prose sentence ends it."""
        if self._current is None:
            return False
        starts_new_paragraph = (
            self._sentence_complete and self._current.kind == "prose" and not _LIST_ITEM.match(line)
        )
        return not starts_new_paragraph

    def _start(self, page: int | None, kind: str, line: str) -> None:
        self._close()
        self._current = _Unit(self._section, page, kind, line)

    def _close(self) -> None:
        if self._current is not None and self._current.text.strip():
            self.units.append(self._current)
        self._current = None
        self._sentence_complete = False

    def _keep_unconfirmed_heading(self) -> None:
        """The guess had no body after it: it was content, not a heading, so keep its text."""
        if self._unconfirmed is not None:
            text, page, section = self._unconfirmed
            self.units.append(_Unit(section, page, "prose", text))
            self._unconfirmed = None


def _build_units(lines: list[tuple[int | None, str]]) -> list[_Unit]:
    builder = _UnitBuilder()
    for page, line in lines:
        builder.add(page, line)
    return builder.finish()


# --- step 3: units -> chunks --------------------------------------------------------------
def _can_merge(previous: _Unit, unit: _Unit) -> bool:
    if previous.section != unit.section:
        return False
    if len(previous.text) < MIN_CLAUSE_CHARS:
        return True
    both_prose = previous.kind == unit.kind == "prose"
    return both_prose and len(previous.text) + len(unit.text) < TARGET_CHARS


def _pack(units: list[_Unit]) -> list[ChunkDraft]:
    merged: list[_Unit] = []
    for unit in units:
        if merged and _can_merge(merged[-1], unit):
            merged[-1].text = f"{merged[-1].text} {unit.text}"
            merged[-1].kind = unit.kind
        else:
            merged.append(replace(unit))
    return [chunk for unit in merged for chunk in _emit(unit)]


def _emit(unit: _Unit) -> list[ChunkDraft]:
    prefix = f"{unit.section}: " if unit.section else ""
    return [ChunkDraft(prefix + piece, unit.page, unit.section) for piece in _split_long(unit.text)]


def _split_long(text: str) -> list[str]:
    """Split on sentence boundaries into pieces of at most MAX_CHARS."""
    if len(text) <= MAX_CHARS:
        return [text]
    pieces: list[str] = []
    current = ""
    for sentence in _SENTENCE_END.split(text):
        while len(sentence) > MAX_CHARS:  # a single run-on sentence: cut at the last space
            cut = sentence.rfind(" ", 0, MAX_CHARS)
            if cut <= 0:
                cut = MAX_CHARS
            pieces.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if current and len(current) + 1 + len(sentence) > MAX_CHARS:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def _dedupe(chunks: list[ChunkDraft]) -> list[ChunkDraft]:
    """Drop exact repeats (boilerplate pasted twice) while keeping first-seen order."""
    seen: set[str] = set()
    unique = []
    for chunk in chunks:
        key = " ".join(chunk.content.split()).casefold()
        if key not in seen:
            seen.add(key)
            unique.append(chunk)
    return unique
