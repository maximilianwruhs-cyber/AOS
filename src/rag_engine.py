"""
AOS RAG Engine — 100% Local Document Intelligence
Ingests documents via LiteParse, embeds with Ollama, stores in pgvector,
and queries with a local LLM. Zero cloud dependencies.
"""
import os
import subprocess
import shutil
from pathlib import Path

from llama_index.core import (
    VectorStoreIndex,
    StorageContext,
    Settings,
    Document,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.postgres import PGVectorStore
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama

from config import (
    PGVECTOR_CONN_STRING,
    PGVECTOR_DB,
    PGVECTOR_HOST,
    PGVECTOR_PORT,
    PGVECTOR_USER,
    PGVECTOR_PASSWORD,
    INGRESS_DIR,
    RAG_EMBED_MODEL,
    RAG_LLM_MODEL,
)

# ─── Table / Collection Name ─────────────────────────────────────────────────
TABLE_NAME = "aos_documents"
EMBED_DIM = 768  # nomic-embed-text default


# ─── LiteParse Integration ────────────────────────────────────────────────────
def parse_document(file_path: str) -> str:
    """Parse a document using LiteParse and return spatial text."""
    file_path = Path(file_path).resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"Document not found: {file_path}")

    liteparse_bin = shutil.which("liteparse")
    if liteparse_bin is None:
        raise RuntimeError(
            "LiteParse not found. Install with: npm i -g @llamaindex/liteparse"
        )

    result = subprocess.run(
        [liteparse_bin, str(file_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        raise RuntimeError(f"LiteParse failed: {result.stderr.strip()}")

    return result.stdout


# ─── Vector Store Setup ───────────────────────────────────────────────────────
def get_vector_store() -> PGVectorStore:
    """Create a PGVectorStore connection to the local pgvector database."""
    return PGVectorStore.from_params(
        database=PGVECTOR_DB,
        host=PGVECTOR_HOST,
        port=str(PGVECTOR_PORT),
        user=PGVECTOR_USER,
        password=PGVECTOR_PASSWORD,
        table_name=TABLE_NAME,
        embed_dim=EMBED_DIM,
    )


def _configure_llm_settings():
    """Configure LlamaIndex global settings with local Ollama models."""
    Settings.embed_model = OllamaEmbedding(model_name=RAG_EMBED_MODEL)
    Settings.llm = Ollama(model=RAG_LLM_MODEL, request_timeout=120.0)
    Settings.node_parser = SentenceSplitter(chunk_size=512, chunk_overlap=64)


# ─── Ingestion Pipeline ──────────────────────────────────────────────────────
def ingest(file_path: str) -> dict:
    """
    Full ingestion pipeline:
    1. Parse document via LiteParse (spatial text extraction)
    2. Chunk and embed via Ollama (nomic-embed-text)
    3. Store in local pgvector database

    Returns:
        dict with status, filename, and chunk count.
    """
    _configure_llm_settings()

    # Step 1: Parse
    print(f"📄 Parsing: {file_path}")
    raw_text = parse_document(file_path)
    if not raw_text.strip():
        raise ValueError("LiteParse returned empty output for this document.")

    filename = Path(file_path).name
    doc = Document(text=raw_text, metadata={"source": filename})

    # Step 2 & 3: Embed + Store
    print(f"🔗 Connecting to pgvector...")
    vector_store = get_vector_store()
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    print(f"🧮 Embedding and storing chunks...")
    index = VectorStoreIndex.from_documents(
        [doc],
        storage_context=storage_context,
        show_progress=True,
    )

    node_count = len(index.docstore.docs)
    print(f"✅ Ingested '{filename}' → {node_count} chunks stored in pgvector.")

    return {
        "status": "success",
        "filename": filename,
        "chunks": node_count,
    }


# ─── Query Pipeline ──────────────────────────────────────────────────────────
def query(question: str, top_k: int = 5) -> dict:
    """
    Full query pipeline:
    1. Embed the question via Ollama
    2. Search pgvector for relevant chunks
    3. Generate answer with local LLM

    Returns:
        dict with answer text and source nodes.
    """
    _configure_llm_settings()

    print(f"🔍 Querying: {question}")
    vector_store = get_vector_store()
    index = VectorStoreIndex.from_vector_store(vector_store=vector_store)

    query_engine = index.as_query_engine(similarity_top_k=top_k)
    response = query_engine.query(question)

    sources = []
    for node in response.source_nodes:
        sources.append({
            "text": node.text[:200] + "..." if len(node.text) > 200 else node.text,
            "score": round(node.score, 4) if node.score else None,
            "source": node.metadata.get("source", "unknown"),
        })

    print(f"✅ Answer generated from {len(sources)} source chunks.")

    return {
        "answer": str(response),
        "sources": sources,
    }


# ─── CLI Entry Point ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage:")
        print("  python rag_engine.py ingest <file_path>")
        print('  python rag_engine.py query "Your question"')
        sys.exit(1)

    action = sys.argv[1]

    if action == "ingest":
        result = ingest(sys.argv[2])
        print(result)
    elif action == "query":
        result = query(sys.argv[2])
        print(f"\n💬 Answer:\n{result['answer']}")
        if result["sources"]:
            print(f"\n📚 Sources ({len(result['sources'])}):")
            for s in result["sources"]:
                print(f"  - [{s['source']}] (score: {s['score']})")
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)
