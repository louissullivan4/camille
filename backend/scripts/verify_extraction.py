"""
Manual verification script for Phase 3 extraction pipeline.

Reads all .txt documents from a test_data company folder, runs them through
extract_all_dimensions, pipes findings into score_assessment, and prints a
structured JSON report you can share.

Usage (from backend/):
    python scripts/verify_extraction.py company_b_quickhire
    python scripts/verify_extraction.py company_a_greenscore
    python scripts/verify_extraction.py company_c_autoclaim

    # Save output to file:
    python scripts/verify_extraction.py company_b_quickhire > ../results_quickhire.json

Requires ANTHROPIC_API_KEY set in .env or environment.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Ensure backend/app is importable when running from backend/
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings  # noqa: E402 — must come after sys.path fix
from app.llm.client import get_anthropic_client
from app.services.document_processor import chunk_text, extract_text_from_file
from app.services.governance_extractor import extract_all_dimensions
from app.services.scoring_engine import score_assessment


async def run(company: str) -> None:
    test_data_dir = Path(__file__).parent.parent.parent / "test_data" / company

    if not test_data_dir.exists():
        print(f"ERROR: {test_data_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    if not settings.ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY is not set in .env", file=sys.stderr)
        sys.exit(1)

    # --- Load and chunk all .txt documents ---
    doc_files = sorted(test_data_dir.glob("*.txt"))
    if not doc_files:
        print(f"ERROR: No .txt files found in {test_data_dir}", file=sys.stderr)
        sys.exit(1)

    all_chunks: list[str] = []
    loaded_docs: list[dict] = []

    for doc_path in doc_files:
        raw_bytes = doc_path.read_bytes()
        text = extract_text_from_file(raw_bytes, doc_path.name)
        chunks = chunk_text(text, chunk_size=1000, overlap=200)
        # Tag each chunk with its source filename so the extractor can apply
        # document-balanced filtering (prevents early-alphabetical docs from
        # monopolising the keyword-match slots).
        tagged = [f"[Source: {doc_path.name}]\n{chunk}" for chunk in chunks]
        all_chunks.extend(tagged)
        loaded_docs.append({"file": doc_path.name, "chars": len(text), "chunks": len(chunks)})

    # --- Run extraction ---
    client = get_anthropic_client()
    findings = await extract_all_dimensions(all_chunks, client)

    # --- Score ---
    result = score_assessment(findings)

    # --- Build output ---
    output = {
        "company": company,
        "documents_loaded": loaded_docs,
        "total_chunks": len(all_chunks),
        "overall_score": round(result.overall_score, 2),
        "risk_tier": result.risk_tier,
        "dimension_scores": {
            dim: {
                "score": round(ds.score, 2),
                "max_score": ds.max_score,
                "flags": ds.flags,
            }
            for dim, ds in result.dimension_scores.items()
        },
        "all_flags": result.all_flags,
        "raw_findings": findings,
    }

    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    company = sys.argv[1] if len(sys.argv) > 1 else "company_b_quickhire"
    asyncio.run(run(company))
