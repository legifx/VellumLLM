from server.models import Chunk, RetrievedChunk
from server.prompt import build_prompt


def _rc(text, name, loc, score):
    return RetrievedChunk(
        chunk=Chunk(source_id=1, ordinal=0, text=text, modality="document", locator=loc),
        source_name=name, source_path="/x/" + name, score=score,
    )


def test_prompt_includes_grounding_rules_and_markers():
    chunks = [_rc("Revenue grew 42%.", "report.pdf", "p. 1", 0.9),
              _rc("Risks: supply chain.", "report.pdf", "p. 2", 0.7)]
    prompt, citations = build_prompt("How did revenue change?", chunks)
    assert "ONLY" in prompt
    assert "[S1]" in prompt and "[S2]" in prompt
    assert "report.pdf, p. 1" in prompt
    assert len(citations) == 2
    assert citations[0].source_name == "report.pdf"
    assert citations[0].locator == "p. 1"


def test_prompt_handles_no_sources():
    prompt, citations = build_prompt("anything?", [])
    assert citations == []
    assert "no sources matched" in prompt
