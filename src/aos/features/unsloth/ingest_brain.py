#!/usr/bin/env python3
"""
AOS Brain Auto-Ingest Layer

Scans Antigravity conversation artifacts (walkthroughs, implementation plans,
audit reports, architecture docs) and converts them into structured training
data for Unsloth fine-tuning.

Sources:
  1. Antigravity brain artifacts (~/.gemini/antigravity/brain/*/walkthrough.md, etc.)
  2. Existing AOS_Brain/02_Memory_Logs/*.md (preserved, not duplicated)
  3. Future: ARC-AGI reasoning tasks, code diffs, etc.

Output:
  - AOS_Brain/02_Memory_Logs/auto_ingest_*.md — one file per ingested artifact
  - AOS_Brain/02_Memory_Logs/.ingest_manifest.json — tracks what's been ingested

Usage:
  python ingest_brain.py                  # Incremental ingest (skip already-processed)
  python ingest_brain.py --force          # Re-ingest everything
  python ingest_brain.py --dry-run        # Show what would be ingested
  python ingest_brain.py --stats          # Show current dataset statistics
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent.resolve()
AOS_ROOT = SCRIPT_DIR.parent.parent.parent.parent  # src/aos/features/unsloth → AOS/
BRAIN_DIR = AOS_ROOT / "AOS_Brain" / "02_Memory_Logs"
ANTIGRAVITY_BRAIN = Path.home() / ".gemini" / "antigravity" / "brain"
MANIFEST_FILE = BRAIN_DIR / ".ingest_manifest.json"

# Artifact types worth ingesting (skip task.md — it's just TODO lists)
ARTIFACT_TYPES = {
    "walkthrough.md": "walkthrough",
    "implementation_plan.md": "implementation_plan",
    "audit_report.md": "security_audit",
    "drift_analysis.md": "architecture_analysis",
    "leaderboard_analysis.md": "benchmark_analysis",
    "medusa_architecture.md": "architecture_design",
    "setup_log.md": "setup_documentation",
}

# Minimum content length to be worth ingesting (skip trivially small files)
MIN_CONTENT_LENGTH = 200

# System prompts for different artifact types (used in ChatML wrapping)
SYSTEM_PROMPTS = {
    "walkthrough": "You are NemoClaw, documenting completed engineering work with technical precision.",
    "implementation_plan": "You are NemoClaw, creating detailed technical implementation plans for software engineering tasks.",
    "security_audit": "You are NemoClaw, performing OWASP-compliant security audits on codebases.",
    "architecture_analysis": "You are NemoClaw, analyzing software architecture drift and recommending corrections.",
    "architecture_design": "You are NemoClaw, designing high-performance inference architectures for local AI systems.",
    "benchmark_analysis": "You are NemoClaw, analyzing model benchmark results and recommending optimizations.",
    "setup_documentation": "You are NemoClaw, documenting system setup and configuration procedures.",
    "generic": "You are NemoClaw, a sovereign AI coding assistant specializing in local AI infrastructure.",
}

USER_PROMPTS = {
    "walkthrough": "Document what was accomplished in this engineering session.",
    "implementation_plan": "Create an implementation plan for the following task.",
    "security_audit": "Perform a security audit of this codebase.",
    "architecture_analysis": "Analyze the current architecture and identify drift.",
    "architecture_design": "Design the architecture for this system component.",
    "benchmark_analysis": "Analyze these benchmark results and recommend improvements.",
    "setup_documentation": "Document the setup procedure for this system.",
    "generic": "Provide a technical analysis of the following.",
}


def load_manifest() -> dict:
    """Load the ingest manifest tracking previously processed files."""
    if MANIFEST_FILE.exists():
        with open(MANIFEST_FILE, "r") as f:
            return json.load(f)
    return {"ingested": {}, "last_run": None, "version": 1}


def save_manifest(manifest: dict):
    """Persist the ingest manifest."""
    manifest["last_run"] = datetime.now().isoformat()
    BRAIN_DIR.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)


def content_hash(content: str) -> str:
    """Generate a hash of file content for change detection."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def clean_content(content: str) -> str:
    """Strip artifact metadata, file links, and non-training noise from content."""
    # Remove file:/// links (they're absolute paths, useless for training)
    content = re.sub(r'\[([^\]]+)\]\(file:///[^)]+\)', r'\1', content)
    # Remove render_diffs directives
    content = re.sub(r'render_diffs\([^)]+\)', '', content)
    # Remove image embeds (binary references)
    content = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'[Image: \1]', content)
    # Collapse excessive blank lines
    content = re.sub(r'\n{3,}', '\n\n', content)
    return content.strip()


def wrap_chatml(content: str, artifact_type: str) -> str:
    """Wrap cleaned content in ChatML format for Unsloth training."""
    system = SYSTEM_PROMPTS.get(artifact_type, SYSTEM_PROMPTS["generic"])
    user = USER_PROMPTS.get(artifact_type, USER_PROMPTS["generic"])

    return (
        f"<|im_start|>system\n{system}<|im_end|>\n"
        f"<|im_start|>user\n{user}<|im_end|>\n"
        f"<|im_start|>assistant\n{content}<|im_end|>"
    )


def discover_artifacts() -> list[dict]:
    """Scan Antigravity brain for ingestible artifacts."""
    artifacts = []

    if not ANTIGRAVITY_BRAIN.exists():
        print(f"WARNING: Antigravity brain not found at {ANTIGRAVITY_BRAIN}")
        return artifacts

    for conv_dir in sorted(ANTIGRAVITY_BRAIN.iterdir()):
        if not conv_dir.is_dir():
            continue
        conv_id = conv_dir.name

        for filename, artifact_type in ARTIFACT_TYPES.items():
            filepath = conv_dir / filename
            if filepath.exists():
                content = filepath.read_text(encoding="utf-8", errors="replace")
                if len(content) >= MIN_CONTENT_LENGTH:
                    artifacts.append({
                        "path": str(filepath),
                        "conv_id": conv_id,
                        "filename": filename,
                        "type": artifact_type,
                        "content": content,
                        "hash": content_hash(content),
                        "size": len(content),
                    })

        # Also pick up any non-standard .md files (custom artifacts)
        for md_file in conv_dir.glob("*.md"):
            if md_file.name in ARTIFACT_TYPES or md_file.name == "task.md":
                continue
            content = md_file.read_text(encoding="utf-8", errors="replace")
            if len(content) >= MIN_CONTENT_LENGTH:
                artifacts.append({
                    "path": str(md_file),
                    "conv_id": conv_id,
                    "filename": md_file.name,
                    "type": "generic",
                    "content": content,
                    "hash": content_hash(content),
                    "size": len(content),
                })

    return artifacts


def ingest_artifact(artifact: dict) -> str:
    """Convert an artifact to a training-ready markdown file in the Brain vault."""
    cleaned = clean_content(artifact["content"])
    # Don't re-wrap in ChatML for the .md file — the training script does that.
    # Just save the clean content with metadata header.
    output = (
        f"---\n"
        f"source: antigravity_conversation\n"
        f"conversation_id: {artifact['conv_id']}\n"
        f"artifact_type: {artifact['type']}\n"
        f"original_file: {artifact['filename']}\n"
        f"ingested_at: {datetime.now().isoformat()}\n"
        f"content_hash: {artifact['hash']}\n"
        f"---\n\n"
        f"{cleaned}"
    )

    # Generate output filename
    short_id = artifact["conv_id"][:8]
    safe_name = artifact["filename"].replace(".md", "")
    output_name = f"auto_ingest_{short_id}_{safe_name}.md"
    output_path = BRAIN_DIR / output_name

    output_path.write_text(output, encoding="utf-8")
    return str(output_path)


def run_stats():
    """Print dataset statistics."""
    manual_files = list(BRAIN_DIR.glob("*.md"))
    auto_files = [f for f in manual_files if f.name.startswith("auto_ingest_")]
    manual_files = [f for f in manual_files if not f.name.startswith("auto_ingest_")]

    total_chars = sum(f.stat().st_size for f in BRAIN_DIR.glob("*.md"))
    artifacts = discover_artifacts()

    print("═══════════════════════════════════════════")
    print("  AOS Brain Training Data Statistics")
    print("═══════════════════════════════════════════")
    print(f"  Manual insights:    {len(manual_files)}")
    print(f"  Auto-ingested:      {len(auto_files)}")
    print(f"  Total files:        {len(manual_files) + len(auto_files)}")
    print(f"  Total size:         {total_chars / 1024:.1f} KB")
    print(f"  ─────────────────────────────────────────")
    print(f"  Available artifacts: {len(artifacts)} (in Antigravity brain)")
    manifest = load_manifest()
    pending = [a for a in artifacts if a["hash"] not in manifest.get("ingested", {})]
    print(f"  Pending ingest:      {pending and len(pending) or 0}")
    print(f"  Last ingest run:     {manifest.get('last_run', 'Never')}")
    print("═══════════════════════════════════════════")


def main():
    parser = argparse.ArgumentParser(description="AOS Brain Auto-Ingest Layer")
    parser.add_argument("--force", action="store_true", help="Re-ingest all artifacts")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be ingested")
    parser.add_argument("--stats", action="store_true", help="Show dataset statistics")
    args = parser.parse_args()

    if args.stats:
        run_stats()
        return

    BRAIN_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    artifacts = discover_artifacts()

    if not artifacts:
        print("No artifacts found in Antigravity brain.")
        return

    # Filter already-ingested (unless --force)
    if args.force:
        pending = artifacts
    else:
        pending = [a for a in artifacts if a["hash"] not in manifest.get("ingested", {})]

    if not pending:
        print(f"All {len(artifacts)} artifacts already ingested. Use --force to re-ingest.")
        return

    if args.dry_run:
        print(f"Would ingest {len(pending)} artifacts:")
        for a in pending:
            print(f"  [{a['type']}] {a['conv_id'][:8]}/{a['filename']} ({a['size']} bytes)")
        return

    # Ingest
    print(f"Ingesting {len(pending)} artifacts from {len(set(a['conv_id'] for a in pending))} conversations...")
    ingested_count = 0
    for artifact in pending:
        output_path = ingest_artifact(artifact)
        manifest["ingested"][artifact["hash"]] = {
            "source": artifact["path"],
            "output": output_path,
            "type": artifact["type"],
            "ingested_at": datetime.now().isoformat(),
        }
        ingested_count += 1
        print(f"  ✓ [{artifact['type']}] {artifact['conv_id'][:8]}/{artifact['filename']}")

    save_manifest(manifest)
    print(f"\nIngested {ingested_count} artifacts. Total training files: {len(list(BRAIN_DIR.glob('*.md')))}")


if __name__ == "__main__":
    main()
