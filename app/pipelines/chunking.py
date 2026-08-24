from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from typing import List, Optional, Tuple

try:
    import tiktoken
    _ENC = tiktoken.get_encoding("cl100k_base")
except Exception:  # pragma: no cover
    _ENC = None


# --------------------------------------------------------------------------
# Token counting
# --------------------------------------------------------------------------

def count_tokens(text: str) -> int:
    """Single-string count. Prefer count_tokens_batch when counting many
    strings — it avoids per-call tiktoken overhead."""
    if not text:
        return 0
    if _ENC is not None:
        return len(_ENC.encode_ordinary(text))
    words = text.split()
    return max(1, int(len(words) * 1.3))


@lru_cache(maxsize=4096)
def _count_tokens_cached(text: str) -> int:
    # Cheap win: headings and short atoms recur a lot across a document.
    return count_tokens(text)


def count_tokens_batch(texts: List[str]) -> List[int]:
    """Batch-tokenize many strings in one tiktoken call instead of N calls."""
    if not texts:
        return []
    if _ENC is not None:
        return [len(t) for t in _ENC.encode_ordinary_batch(texts)]
    return [count_tokens(t) for t in texts]


def _decode_to_token_limit(text: str, max_tokens: int) -> str:
    """Truncate text to max_tokens without repeatedly re-encoding."""
    if _ENC is None:
        words = text.split()
        while words and count_tokens(" ".join(words)) > max_tokens:
            words.pop()
        return " ".join(words).strip()

    tokens = _ENC.encode_ordinary(text)
    if len(tokens) <= max_tokens:
        return text.strip()
    truncated = _ENC.decode(tokens[:max_tokens])
    # avoid cutting mid-word
    if truncated and not truncated.endswith((" ", "\n")):
        truncated = truncated.rsplit(" ", 1)[0]
    return truncated.strip()


# --------------------------------------------------------------------------
# Step 1: unchanged (regex block splitting is already cheap/linear)
# --------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)")
_FENCE_RE = re.compile(r"^```")


def _split_into_blocks(md: str) -> List[Tuple[str, Optional[Tuple[int, str]]]]:
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
# Step 2: auto summary — now O(1) encodes instead of O(n)
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
    summary = _decode_to_token_limit(summary, max_tokens)
    if summary and not summary.endswith((".", "!", "?")):
        summary += "..."
    return summary


# --------------------------------------------------------------------------
# Step 3: pack blocks into parents — batch-count all block tokens upfront
# --------------------------------------------------------------------------

def _build_parents(
    blocks: List[Tuple[str, Optional[Tuple[int, str]]]],
    parent_min: int,
    parent_max: int,
) -> List[Tuple[str, str]]:
    parents: List[Tuple[str, str]] = []
    stack: List[Tuple[int, str]] = []
    buf: List[str] = []
    buf_tokens = 0
    buf_heading_path = ""

    # One batched tiktoken call for every block, instead of one call per block.
    block_texts = [b[0] for b in blocks]
    block_tok_counts = count_tokens_batch(block_texts)

    def flush():
        nonlocal buf, buf_tokens
        if buf:
            parents.append(("\n\n".join(buf).strip(), buf_heading_path))
            buf = []
            buf_tokens = 0

    for (text, heading), block_tokens in zip(blocks, block_tok_counts):
        if heading:
            level, title = heading
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            if buf_tokens >= parent_min:
                flush()
            if not buf:
                buf_heading_path = _heading_path(stack)
            buf.append(text)
            buf_tokens += block_tokens
            continue

        if buf_tokens + block_tokens > parent_max and buf_tokens >= parent_min:
            flush()
            buf_heading_path = _heading_path(stack)

        if not buf:
            buf_heading_path = _heading_path(stack)

        buf.append(text)
        buf_tokens += block_tokens

        if block_tokens >= parent_max:
            flush()
            buf_heading_path = _heading_path(stack)

    flush()
    return parents


# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# Step 4: Multilingual children splitting & atom packing
# --------------------------------------------------------------------------

# Universal sentence boundary regex:
# Matches standard punctuation (. ! ?), Armenian (։ ՜ ՞ ՝), Arabic/Persian (؟ ۔),
# Hindi/Sanskrit (। ॥), CJK (。 ！？), followed by whitespace/newlines or line breaks.
_SENTENCE_SPLIT_RE = re.compile(
    r"(?:[\.\!\?\u0589\u055C\u055E\u055D\u061F\u06D4\u0964\u0965\u3002\uFF01\uFF1F]+[\s\n]+|\n+)"
)


def _split_atoms(text: str, max_atom_tokens: int = 150) -> List[str]:
    """
    Splits text on multilingual sentence and line boundaries.
    If a sentence or block is still oversized (> max_atom_tokens), it is split
    by word boundaries to prevent any single atom from starving or overflowing
    the chunk packing buffer.
    """
    raw_atoms = _SENTENCE_SPLIT_RE.split(text)
    atoms: List[str] = []

    for a in raw_atoms:
        trimmed = a.strip()
        if not trimmed:
            continue

        # Fast path: short atom
        if len(trimmed) <= max_atom_tokens * 3:
            atoms.append(trimmed)
            continue

        tok_len = count_tokens(trimmed)
        if tok_len <= max_atom_tokens:
            atoms.append(trimmed)
        else:
            # Sub-split oversized atom by whitespace / words
            words = trimmed.split()
            buf: List[str] = []
            buf_tok = 0
            for w in words:
                w_tok = max(1, count_tokens(w))
                if buf and buf_tok + w_tok > max_atom_tokens:
                    atoms.append(" ".join(buf))
                    buf = [w]
                    buf_tok = w_tok
                else:
                    buf.append(w)
                    buf_tok += w_tok
            if buf:
                atoms.append(" ".join(buf))

    return atoms


def _build_children(
    parent_text: str,
    child_min: int,
    child_max: int,
    overlap_ratio: float,
) -> List[Tuple[str, int]]:
    """
    Packs atoms into child chunks (child_min to child_max tokens) with sliding overlap.
    Safely advances without infinite looping on any input text.
    """
    atoms = _split_atoms(parent_text, max_atom_tokens=child_max)
    if not atoms:
        return []

    atom_tokens_list = count_tokens_batch(atoms)

    chunks: List[List[Tuple[str, int]]] = []
    current: List[Tuple[str, int]] = []
    current_tokens = 0
    i = 0

    while i < len(atoms):
        atom, atom_tokens = atoms[i], atom_tokens_list[i]

        # If adding this atom exceeds max and we already have content in current chunk
        if current and (current_tokens + atom_tokens > child_max):
            chunks.append(current)
            target_overlap = int(overlap_ratio * child_max)
            tail: List[Tuple[str, int]] = []
            tail_tokens = 0

            # Calculate overlap tail
            for a, a_tok in reversed(current):
                if tail_tokens + a_tok > target_overlap:
                    break
                tail.insert(0, (a, a_tok))
                tail_tokens += a_tok

            current = tail
            current_tokens = tail_tokens

            # If tail + atom is still too big, start a fresh chunk directly with this atom
            if current and (current_tokens + atom_tokens > child_max):
                chunks.append(current)
                current = []
                current_tokens = 0

            # If current is empty, append atom and advance immediately
            if not current:
                current.append((atom, atom_tokens))
                current_tokens = atom_tokens
                i += 1
            continue

        current.append((atom, atom_tokens))
        current_tokens += atom_tokens
        i += 1

    if current:
        chunks.append(current)

    # Merge very small orphan tail chunk into previous chunk
    if len(chunks) > 1:
        last_tokens = sum(t for _, t in chunks[-1])
        if last_tokens < int(child_min * 0.5):
            chunks[-2].extend(chunks[-1])
            chunks.pop()

    return [
        (" ".join(a for a, _ in c), sum(t for _, t in c))
        for c in chunks
    ]



# --------------------------------------------------------------------------
# Data model (unchanged)
# --------------------------------------------------------------------------

@dataclass
class ChildChunk:
    id: str
    parent_id: str
    text: str
    embedding_text: str
    tokens: int
    heading_path: str
    index_in_parent: int


@dataclass
class ParentChunk:
    id: str
    text: str
    tokens: int
    heading_path: str
    index: int
    children: List[ChildChunk] = field(default_factory=list)


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
            tokens=count_tokens(parent_text),  # one call, one per parent — cheap
            heading_path=heading_path,
            index=p_index,
        )

        for c_index, (child_text, child_tokens) in enumerate(
            _build_children(parent_text, child_min, child_max, overlap_ratio)
        ):
            embedding_text = f"{summary}\n\n{child_text}" if summary else child_text
            parent.children.append(
                ChildChunk(
                    id=str(uuid.uuid4()),
                    parent_id=parent_id,
                    text=child_text,
                    embedding_text=embedding_text,
                    tokens=child_tokens,
                    heading_path=heading_path,
                    index_in_parent=c_index,
                )
            )

        parents.append(parent)

    return {"summary": summary, "parents": parents}