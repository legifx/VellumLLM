"""Prompt construction with strict source grounding.

Builds a system prompt that forbids fabrication and requires citations, plus a
context block of retrieved chunks each tagged with a stable citation marker the
model is told to reuse (e.g. [S1], [S2]).
"""
from __future__ import annotations

from .models import Citation, RetrievedChunk

SYSTEM_PROMPT = """\
You are Local NotebookLM, a strictly source-grounded assistant. You answer ONLY \
using the SOURCES provided below. Follow these rules without exception:

1. Use only information contained in the SOURCES. Do not use outside knowledge.
2. If the answer is not in the SOURCES, say clearly: "This is not covered by the \
provided sources." Do not guess or fabricate.
3. Cite every claim with the bracketed marker of the source it came from, e.g. \
[S1] or [S2]. Place citations inline right after the relevant sentence.
4. If multiple sources support a claim, cite all of them, e.g. [S1][S3].
5. Be concise and faithful to the sources. Do not add information they don't contain.
"""


def build_context_block(chunks: list[RetrievedChunk]) -> tuple[str, list[Citation]]:
    """Return (context_text, citations) with stable [S#] markers."""
    lines: list[str] = []
    citations: list[Citation] = []
    for i, rc in enumerate(chunks, start=1):
        marker = f"S{i}"
        loc = f", {rc.chunk.locator}" if rc.chunk.locator else ""
        header = f"[{marker}] {rc.source_name}{loc}"
        lines.append(f"{header}\n{rc.chunk.text.strip()}")
        snippet = rc.chunk.text.strip().replace("\n", " ")
        citations.append(Citation(
            source_id=rc.chunk.source_id,
            source_name=rc.source_name,
            locator=rc.chunk.locator,
            snippet=(snippet[:240] + "…") if len(snippet) > 240 else snippet,
            score=round(rc.score, 4),
        ))
    return "\n\n".join(lines), citations


def build_prompt(question: str, chunks: list[RetrievedChunk]) -> tuple[str, list[Citation]]:
    """Assemble the full prompt string sent to the CLI and the citation list."""
    context, citations = build_context_block(chunks)
    if not context:
        context = "(no sources matched this question)"
    prompt = (
        f"{SYSTEM_PROMPT}\n"
        f"=================== SOURCES ===================\n"
        f"{context}\n"
        f"================= END SOURCES =================\n\n"
        f"User question: {question}\n\n"
        f"Answer using only the sources above, with [S#] citations:"
    )
    return prompt, citations
