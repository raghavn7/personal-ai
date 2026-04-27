import os

from llama_index.core import SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.core import Settings
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama

# Point this at your exported data folder
DATA_DIR = "<your-data-directory-to-ingest-data>"
INDEX_DIR = "<your-index-directory>"

# Configure models
Settings.llm = Ollama(
    model="command-r:35b",
    request_timeout=300.0
)
Settings.embed_model = OllamaEmbedding(
    model_name="nomic-embed-text"
)

print("Loading your data...")
documents = SimpleDirectoryReader(
    DATA_DIR,
    recursive=True,
    required_exts=[".txt", ".md", ".pdf", ".eml"]
).load_data()

print(f"Indexing {len(documents)} documents...")
index = VectorStoreIndex.from_documents(
    documents,
    show_progress=True
)
index.storage_context.persist(persist_dir=INDEX_DIR)
print("Done! Index saved to", INDEX_DIR)