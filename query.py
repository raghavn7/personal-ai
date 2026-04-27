import httpx
from llama_index.core import StorageContext, load_index_from_storage
from llama_index.core import Settings
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
import ollama as ollama_client

INDEX_DIR = "<your-index-directory>"

timeout = httpx.Timeout(
    connect=30.0,       # time to establish connection
    read=900.0,         # time to wait for response (15 min)
    write=30.0,         # time to send request
    pool=30.0           # time to get connection from pool
)

Settings.llm = Ollama(
    model="qwen2.5:14b",
    request_timeout=900.0,
    http_client=httpx.Client(timeout=timeout),
)
Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")

storage_context = StorageContext.from_defaults(persist_dir=INDEX_DIR)
index = load_index_from_storage(storage_context)
query_engine = index.as_query_engine(similarity_top_k=5)

# Warm up the model before entering query loop
print("Warming up model...")
ollama_client.chat(
    model="qwen2.5:14b",
    messages=[{"role": "user", "content": "hi"}],
    options={"num_predict": 1}   # generate just 1 token — fast
)
print("Model ready.")

print("Your personal AI is ready. Ask anything.")
while True:
    q = input("\nYou: ")
    if q.lower() in ["exit", "quit"]:
        break
    response = query_engine.query(q)
    print(f"\nAI: {response}")