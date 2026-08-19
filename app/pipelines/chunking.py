from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

try:
    import tiktoken
    _ENC = tiktoken.get_encoding("cl100k_base")
except Exception:  # pragma: no cover - fallback if tiktoken unavailable
    _ENC = None


# --------------------------------------------------------------------------
# Token counting
# --------------------------------------------------------------------------

def count_tokens(text: str) -> int:
    if not text:
        return 0
    if _ENC is not None:
        return len(_ENC.encode(text))
    # Rough fallback: ~1.3 tokens per whitespace-split word.
    words = text.split()
    return max(1, int(len(words) * 1.3))


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------

@dataclass
class ChildChunk:
    id: str
    parent_id: str
    text: str                 # raw chunk text
    embedding_text: str       # text + prepended doc summary (for vector search)
    tokens: int
    heading_path: str
    index_in_parent: int


@dataclass
class ParentChunk:
    id: str
    text: str                 # full parent text, fed to the LLM at answer time
    tokens: int
    heading_path: str
    index: int
    children: List[ChildChunk] = field(default_factory=list)


# --------------------------------------------------------------------------
# Step 1: Split markdown into structural blocks (headings, paragraphs,
# fenced code blocks, list groups) while tracking heading hierarchy.
# --------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)")
_FENCE_RE = re.compile(r"^```")


def _split_into_blocks(md: str) -> List[Tuple[str, Optional[Tuple[int, str]]]]:
    """
    Returns a list of (block_text, heading_or_None) tuples.
    heading_or_None is (level, title) when the block IS a heading line.
    """
    lines = md.split("\n")
    blocks: List[Tuple[str, Optional[Tuple[int, str]]]] = []
    buf: List[str] = []
    in_code = False

    def flush():
        if buf:
            text = "\n".join(buf).strip()
            if text:
                blocks.append((text, None))
            buf.clear()

    for line in lines:
        if _FENCE_RE.match(line.strip()):
            buf.append(line)
            in_code = not in_code
            if not in_code:
                flush()
            continue

        if in_code:
            buf.append(line)
            continue

        heading_match = _HEADING_RE.match(line)
        if heading_match:
            flush()
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            blocks.append((line.strip(), (level, title)))
            continue

        if line.strip() == "":
            flush()
            continue

        buf.append(line)

    flush()
    return blocks


def _heading_path(stack: List[Tuple[int, str]]) -> str:
    return " > ".join(title for _, title in stack)


# --------------------------------------------------------------------------
# Step 2: Auto-extract a short document-level summary for contextual
# enrichment (used when the caller doesn't supply their own).
# --------------------------------------------------------------------------

def _auto_summary(md: str, max_tokens: int = 50) -> str:
    title = ""
    first_para = ""

    for block, heading in _split_into_blocks(md):
        if heading and not title:
            title = heading[1]
            continue
        if not heading and not first_para:
            first_para = re.sub(r"\s+", " ", block).strip()
        if title and first_para:
            break

    summary = f"{title}. {first_para}" if title else first_para
    # Trim to max_tokens without cutting mid-word.
    words = summary.split()
    while words and count_tokens(" ".join(words)) > max_tokens:
        words.pop()
    summary = " ".join(words).strip()
    if summary and not summary.endswith((".", "!", "?")):
        summary += "..."
    return summary


# --------------------------------------------------------------------------
# Step 3: Pack blocks into parent chunks (500-1000 tokens by default),
# preferring not to split a block, and tracking heading path per parent.
# --------------------------------------------------------------------------

def _build_parents(
    blocks: List[Tuple[str, Optional[Tuple[int, str]]]],
    parent_min: int,
    parent_max: int,
) -> List[Tuple[str, str]]:
    """Returns list of (parent_text, heading_path)."""
    parents: List[Tuple[str, str]] = []
    stack: List[Tuple[int, str]] = []
    buf: List[str] = []
    buf_tokens = 0
    buf_heading_path = ""

    def flush():
        nonlocal buf, buf_tokens
        if buf:
            parents.append(("\n\n".join(buf).strip(), buf_heading_path))
            buf = []
            buf_tokens = 0

    for text, heading in blocks:
        if heading:
            level, title = heading
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            # A new heading is a natural break point once we've hit parent_min.
            if buf_tokens >= parent_min:
                flush()
            if not buf:
                buf_heading_path = _heading_path(stack)
            buf.append(text)
            buf_tokens += count_tokens(text)
            continue

        block_tokens = count_tokens(text)

        if buf_tokens + block_tokens > parent_max and buf_tokens >= parent_min:
            flush()
            buf_heading_path = _heading_path(stack)

        if not buf:
            buf_heading_path = _heading_path(stack)

        buf.append(text)
        buf_tokens += block_tokens

        # A single oversized block (e.g. huge code sample) becomes its own
        # parent immediately so later chunks aren't starved.
        if block_tokens >= parent_max:
            flush()
            buf_heading_path = _heading_path(stack)

    flush()
    return parents


# --------------------------------------------------------------------------
# Step 4: Split each parent into overlapping child chunks (100-200 tokens),
# packing on sentence/line boundaries and carrying an overlap tail forward.
# --------------------------------------------------------------------------

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\[`])|\n+")


def _split_atoms(text: str) -> List[str]:
    atoms = _SENTENCE_SPLIT_RE.split(text)
    return [a.strip() for a in atoms if a.strip()]


def _build_children(
    parent_text: str,
    child_min: int,
    child_max: int,
    overlap_ratio: float,
) -> List[str]:
    atoms = _split_atoms(parent_text)
    if not atoms:
        return []

    chunks: List[List[str]] = []
    current: List[str] = []
    current_tokens = 0
    i = 0

    while i < len(atoms):
        atom = atoms[i]
        atom_tokens = count_tokens(atom)

        if current and current_tokens + atom_tokens > child_max:
            chunks.append(current)
            # Carry an overlap tail (~overlap_ratio of child_max) into the
            # next chunk so context isn't severed at the boundary.
            target_overlap = overlap_ratio * child_max
            tail: List[str] = []
            tail_tokens = 0
            for a in reversed(current):
                a_tok = count_tokens(a)
                if tail_tokens + a_tok > target_overlap:
                    break
                tail.insert(0, a)
                tail_tokens += a_tok
            current = tail
            current_tokens = tail_tokens
            continue  # retry same atom against the fresh (overlapped) buffer

        current.append(atom)
        current_tokens += atom_tokens
        i += 1

    if current:
        chunks.append(current)

    # Merge a too-small trailing chunk into its predecessor to avoid orphans.
    if len(chunks) > 1:
        last_tokens = count_tokens(" ".join(chunks[-1]))
        if last_tokens < child_min * 0.5:
            chunks[-2].extend(chunks[-1])
            chunks.pop()

    return [" ".join(c) for c in chunks]


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def chunk_markdown(
    markdown_text: str,
    parent_token_range: Tuple[int, int] = (500, 1000),
    child_token_range: Tuple[int, int] = (100, 200),
    overlap_ratio: float = 0.15,
    doc_summary: Optional[str] = None,
) -> dict:
    """
    Chunk markdown text using parent-child retrieval + contextual enrichment
    + sliding overlap.

    Args:
        markdown_text: raw markdown source.
        parent_token_range: (min, max) tokens per parent chunk.
        child_token_range: (min, max) tokens per child chunk.
        overlap_ratio: fraction (0.10-0.20 recommended) of a child chunk's
            token budget carried forward into the next child as overlap.
        doc_summary: optional 1-2 sentence document summary to prepend to
            every child's embedding_text. If omitted, one is auto-extracted
            from the document's first heading + first paragraph.

    Returns:
        {
            "summary": str,
            "parents": List[ParentChunk],   # parent.children -> List[ChildChunk]
        }
    """
    parent_min, parent_max = parent_token_range
    child_min, child_max = child_token_range

    summary = doc_summary if doc_summary is not None else _auto_summary(markdown_text)

    blocks = _split_into_blocks(markdown_text)
    raw_parents = _build_parents(blocks, parent_min, parent_max)

    parents: List[ParentChunk] = []
    for p_index, (parent_text, heading_path) in enumerate(raw_parents):
        parent_id = str(uuid.uuid4())
        parent = ParentChunk(
            id=parent_id,
            text=parent_text,
            tokens=count_tokens(parent_text),
            heading_path=heading_path,
            index=p_index,
        )

        child_texts = _build_children(parent_text, child_min, child_max, overlap_ratio)
        for c_index, child_text in enumerate(child_texts):
            embedding_text = f"{summary}\n\n{child_text}" if summary else child_text
            parent.children.append(
                ChildChunk(
                    id=str(uuid.uuid4()),
                    parent_id=parent_id,
                    text=child_text,
                    embedding_text=embedding_text,
                    tokens=count_tokens(child_text),
                    heading_path=heading_path,
                    index_in_parent=c_index,
                )
            )

        parents.append(parent)

    return {"summary": summary, "parents": parents}

