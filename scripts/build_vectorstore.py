"""
Build the Chroma vector store from knowledge base articles.

Run after seed_knowledge_base.py:
    python -m scripts.build_vectorstore

Reads all markdown files from knowledge_base/docs/,
splits them into chunks, embeds them, and stores in Chroma.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter 
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

from app.config import CHROMA_PERSIST_DIR, EMBEDDING_MODEL

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "knowledge_base", "docs")


def load_documents():
    """Load all markdown files from the knowledge base."""
    loader = DirectoryLoader(
        DOCS_DIR,
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
    )
    docs = loader.load()
    print(f"Loaded {len(docs)} documents from {DOCS_DIR}")
    return docs


def chunk_documents(docs):
    """
    Split documents into smaller chunks for embedding.

    Why these settings:
    - chunk_size=500: small enough to be specific, large enough to have context
    - chunk_overlap=50: prevents cutting a sentence in half between chunks
    - separators: splits on headers first, then paragraphs, then sentences
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n## ", "\n\n", "\n", ". ", " "],
    )
    chunks = splitter.split_documents(docs)
    print(f"Split into {len(chunks)} chunks")
    return chunks


def build_vectorstore(chunks):
    """Embed chunks and store in Chroma."""

    # sentence-transformers model runs locally, free, no API key needed
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
    )

    # Clear existing DB if it exists
    if os.path.exists(CHROMA_PERSIST_DIR):
        import shutil
        shutil.rmtree(CHROMA_PERSIST_DIR)
        print(f"Cleared existing vector store at {CHROMA_PERSIST_DIR}")

    # Build and persist
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_PERSIST_DIR,
        collection_name="knowledge_base",
    )

    print(f"Vector store built and saved to {CHROMA_PERSIST_DIR}")
    return vectorstore


def test_search(vectorstore):
    """Quick sanity check — search for a known topic."""
    test_queries = [
        "PDF export not working",
        "how do I reset my password",
        "what is included in the Pro plan",
    ]

    print("\n--- Sanity check ---")
    for query in test_queries:
        results = vectorstore.similarity_search_with_score(query, k=2)
        print(f"\nQuery: \"{query}\"")
        for doc, score in results:
            source = os.path.basename(doc.metadata.get("source", "unknown"))
            preview = doc.page_content[:80].replace("\n", " ")
            print(f"  [{score:.3f}] {source}: {preview}...")


def main():
    if not os.path.exists(DOCS_DIR):
        print(f"Error: {DOCS_DIR} not found. Run seed_knowledge_base.py first.")
        return

    docs = load_documents()
    chunks = chunk_documents(docs)
    vectorstore = build_vectorstore(chunks)
    test_search(vectorstore)

    print(f"\nDone. Vector store ready at {CHROMA_PERSIST_DIR}")


if __name__ == "__main__":
    main()