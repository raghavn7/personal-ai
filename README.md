# Local AI Personal Assistant — Complete Setup Guide

A fully private AI assistant that runs entirely on your Mac. Feed it your emails, messages, notes, and documents, then ask questions in plain English — from your Mac or any device on your home WiFi. Nothing ever leaves your computer.

---

## What You're Building

```
Your Data (emails, notes, messages, PDFs)
        ↓
   nomic-embed-text          ← converts text into searchable vectors (runs once at ingest)
        ↓
     ChromaDB                ← stores vectors locally on your Mac
        ↓
  You ask a question (Mac terminal or phone browser)
        ↓
  nomic-embed-text           ← converts your question into a vector
        ↓
  ChromaDB finds matches     ← retrieves the most relevant chunks of your data
        ↓
  qwen2.5:14b                ← reads those chunks + your question, writes the answer
        ↓
  Answer with citations      ← "Based on your email from March 3rd..."
```

Every step runs on your Mac. No internet required after the one-time model download.

---

## Hardware Requirements

| Spec | Minimum | This Guide |
|---|---|---|
| Chip | Apple Silicon (M1+) | M5 |
| RAM | 16GB | 24GB |
| Free Disk | 50GB | 50GB+ |
| OS | macOS 13+ | macOS 15+ |

**Why Apple Silicon?** M-series chips use unified memory — the CPU and GPU share one memory pool. Your full 24GB is available to the AI model, unlike Windows PCs where GPU VRAM is capped at 8–16GB and separate from system RAM. The M5 also has 153 GB/s memory bandwidth, which directly determines how fast the model generates tokens.

---

## Model Roles — What Each Model Does

Understanding this prevents confusion. There are three models and their roles never swap.

| Model | Used in | Role |
|---|---|---|
| `nomic-embed-text` | `ingest.py` + `server.py` | Converts text into vectors. Used at ingest time AND at query time to convert your question into a vector. Never generates answers. |
| `qwen2.5:14b` | `server.py` only | Reads the retrieved chunks and writes the answer. This is the chat/RAG model. |
| ChromaDB | Both | Not a model — pure math. Finds the closest matching vectors when you ask a question. |

**`ingest.py` never changes** regardless of which chat model you use. Only the chat model in `server.py` ever needs swapping.

### Chat model options (swap anytime in `server.py`)

```python
# Fast, great for everyday questions — recommended default
Settings.llm = Ollama(model="qwen2.5:14b", ...)

# Slower, built specifically for RAG, returns inline citations
Settings.llm = Ollama(model="command-r:35b", ...)

# Slowest, deepest reasoning, best for complex analysis
Settings.llm = Ollama(model="qwen2.5:32b", ...)
```

---

## Software Stack

| Component | Tool | Purpose |
|---|---|---|
| Package manager | Homebrew | Installs developer tools |
| AI runtime | Ollama | Runs all models locally |
| Embedding model | nomic-embed-text | Converts text to vectors |
| Chat model | qwen2.5:14b | Reads retrieved chunks, writes answers |
| RAG framework | LlamaIndex | Wires models + vector DB together |
| Vector database | ChromaDB | Stores and searches your vectors |
| Web server | Flask | Serves the chat UI to your phone |

---

## Folder Structure

```
~/personal-ai/
├── venv/                   ← Python virtual environment (auto-created)
├── my_personal_data/       ← Your exported files go here
│   ├── emails/
│   ├── notes/
│   └── messages/
├── my_index/               ← Vector database (auto-created by ingest.py)
├── ingest.py               ← Run once to build the searchable index
├── server.py               ← Web server — run this for Mac + phone access
└── README.md               ← This file
```

---

## Step 1 — Install Homebrew

Homebrew is a package manager for macOS. It installs developer tools with a single command instead of manually downloading installers.

Open **Terminal** and run:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Takes 2–5 minutes. Follow any prompts. Skip if you already have Homebrew.

Install Python:

```bash
brew install python
```

---

## Step 2 — Install Ollama

Ollama is the engine that runs AI models locally. It starts a local server at `http://localhost:11434` — all processing happens on-device.

```bash
brew install ollama
```

Configure Ollama to listen on your local network (required for phone access) and keep models loaded in memory permanently:

```bash
echo 'export OLLAMA_HOST=0.0.0.0' >> ~/.zshrc
echo 'export OLLAMA_KEEP_ALIVE=-1' >> ~/.zshrc
source ~/.zshrc
```

**What these do:**
- `OLLAMA_HOST=0.0.0.0` — makes Ollama accept connections from any device on your WiFi, not just your Mac
- `OLLAMA_KEEP_ALIVE=-1` — keeps models loaded in RAM permanently instead of unloading after 5 minutes of inactivity (unloading causes slow cold-start timeouts)

Start Ollama (keep this Terminal tab open):

```bash
ollama serve
```

Verify it's running (new Terminal tab):

```bash
curl http://localhost:11434
# Expected: Ollama is running
```

---

## Step 3 — Download the AI Models

Three models to download. One-time only.

**qwen2.5:14b** — your main chat model. Fast, smart, fits comfortably in 24GB RAM with plenty of headroom.

```bash
ollama pull qwen2.5:14b
```

**nomic-embed-text** — the embedding model. Converts your data and questions into vectors. Tiny (137MB) and fast.

```bash
ollama pull nomic-embed-text
```

**Optional — additional chat models** to have available for swapping:

```bash
ollama pull command-r:35b    # better citations, slower (~19GB)
ollama pull qwen2.5:32b      # deeper reasoning, slowest (~18GB)
```

Verify everything downloaded:

```bash
ollama list
```

---

## Step 4 — Set Up Python Virtual Environment

macOS locks its system Python to prevent accidental breakage. The fix is a virtual environment — an isolated Python sandbox inside your project folder.

```bash
mkdir ~/personal-ai && cd ~/personal-ai
```

```bash
python3 -m venv venv
```

Activate it:

```bash
source venv/bin/activate
```

Your Terminal prompt changes to show `(venv)`. **Run this activation command every time you open a new Terminal session before running your scripts.**

Install all dependencies:

```bash
pip install llama-index llama-index-llms-ollama llama-index-embeddings-ollama chromadb flask
```

> **If you see `externally-managed-environment` error:** You forgot to activate the venv. Run `source venv/bin/activate` first, then retry.

---

## Step 5 — Export Your Personal Data

Create the data folder:

```bash
mkdir ~/personal-ai/my_personal_data
```

Place exported files inside it. You can use subfolders — the ingestion script reads recursively.

| Data Type | How to Export |
|---|---|
| Apple Mail | Mail app → Mailbox menu → Export Mailbox → saves as `.mbox` |
| Apple Notes | File → Export → Export as HTML or plain text |
| iMessages | Use [iMazing](https://imazing.com) (free tier) → export as `.txt` |
| WhatsApp | Settings → Chats → Export Chat → saves as `.txt` |
| PDFs & Docs | Copy directly into the folder |

Supported file extensions: `.txt`, `.md`, `.pdf`, `.eml`

---

## Step 6 — Ingest Your Data

Save this as `~/personal-ai/ingest.py`:

```python
from llama_index.core import (
    VectorStoreIndex,
    SimpleDirectoryReader,
    StorageContext,
)
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core import Settings

DATA_DIR = "./my_personal_data"
INDEX_DIR = "./my_index"

Settings.llm = Ollama(model="qwen2.5:14b", request_timeout=300.0)
Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")

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
```

Run it (make sure `(venv)` is active and `ollama serve` is running):

```bash
cd ~/personal-ai
source venv/bin/activate
python3 ingest.py
```

**What this does step by step:**
1. Reads every supported file inside `my_personal_data/` recursively
2. Splits each file into chunks of ~512 tokens (~400 words each)
3. Sends each chunk to `nomic-embed-text` → gets back a vector of 768 numbers representing its meaning
4. Stores all vectors in ChromaDB
5. Saves the entire index to `my_index/` on disk

Run this **once**, or again whenever you add new data. First run can take 30–90 minutes depending on how much data you have. After that, `my_index/` is your permanent searchable database — you never rebuild it unless you add new files.

---

## Step 7 — Run the Web Server

This script serves a mobile-friendly chat UI accessible from any browser on your network. It handles model warm-up, index loading, and all RAG logic in one place.

Save this as `~/personal-ai/server.py`:

```python
import httpx
import ollama as ollama_client
from flask import Flask, request, jsonify, render_template_string
from llama_index.core import StorageContext, load_index_from_storage
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core import Settings

app = Flask(__name__)
INDEX_DIR = "./my_index"

# Generous timeouts across all HTTP layers to prevent cold-start failures
timeout = httpx.Timeout(connect=30.0, read=900.0, write=30.0, pool=30.0)

Settings.llm = Ollama(
    model="qwen2.5:14b",          # swap to command-r:35b or qwen2.5:32b anytime
    request_timeout=900.0,
    http_client=httpx.Client(timeout=timeout),
)
Settings.embed_model = OllamaEmbedding(
    model_name="nomic-embed-text",
    http_client=httpx.Client(timeout=120.0),
)

# Pre-warm: forces the model into RAM before the first real query
print("Warming up model (may take 30-60 seconds on first run)...")
ollama_client.chat(
    model="qwen2.5:14b",
    messages=[{"role": "user", "content": "hi"}],
    options={"num_predict": 1}
)

print("Loading index...")
storage_context = StorageContext.from_defaults(persist_dir=INDEX_DIR)
index = load_index_from_storage(storage_context)
query_engine = index.as_query_engine(
    similarity_top_k=3,        # retrieve 3 most relevant chunks per query
    response_mode="compact",   # compress chunks before sending to model (faster)
)
print("Ready.\n")

HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Personal AI</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, sans-serif; background: #f5f5f5;
           display: flex; flex-direction: column; height: 100dvh; }
    #chat { flex: 1; overflow-y: auto; padding: 16px;
            display: flex; flex-direction: column; gap: 12px; }
    .bubble { max-width: 85%; padding: 12px 16px; border-radius: 18px;
              line-height: 1.5; font-size: 15px; white-space: pre-wrap; }
    .user   { background: #007AFF; color: white;
              align-self: flex-end; border-bottom-right-radius: 4px; }
    .ai     { background: white; color: #1c1c1e;
              align-self: flex-start; border-bottom-left-radius: 4px;
              box-shadow: 0 1px 2px rgba(0,0,0,0.1); }
    .thinking { color: #8e8e93; font-style: italic; font-size: 14px;
                align-self: flex-start; padding: 8px 4px; }
    #form { display: flex; gap: 8px; padding: 12px 16px;
            background: white; border-top: 1px solid #e5e5ea; }
    #input { flex: 1; padding: 10px 14px; border-radius: 22px;
             border: 1px solid #e5e5ea; font-size: 16px; outline: none; }
    #input:focus { border-color: #007AFF; }
    #send { background: #007AFF; color: white; border: none;
            border-radius: 22px; padding: 10px 20px;
            font-size: 16px; cursor: pointer; }
    #send:disabled { background: #c7c7cc; }
  </style>
</head>
<body>
  <div id="chat">
    <div class="bubble ai">Hi! Ask me anything about your emails, notes, and messages.</div>
  </div>
  <div id="form">
    <input id="input" type="text" placeholder="Ask a question..." autocomplete="off" />
    <button id="send" onclick="ask()">Send</button>
  </div>
<script>
  const chat = document.getElementById('chat');
  const input = document.getElementById('input');
  const send = document.getElementById('send');

  input.addEventListener('keydown', e => { if (e.key === 'Enter') ask(); });

  async function ask() {
    const q = input.value.trim();
    if (!q) return;
    input.value = '';
    send.disabled = true;

    append('user', q);
    const thinking = append('thinking', 'Thinking...');

    try {
      const res = await fetch('/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q })
      });
      const data = await res.json();
      thinking.remove();
      append('ai', data.answer || data.error);
    } catch(e) {
      thinking.remove();
      append('ai', 'Error: could not reach the server.');
    }
    send.disabled = false;
  }

  function append(cls, text) {
    const div = document.createElement('div');
    div.className = 'bubble ' + cls;
    div.textContent = text;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
    return div;
  }
</script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML)

@app.route("/query", methods=["POST"])
def query():
    data = request.get_json()
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "No question provided"}), 400
    try:
        response = query_engine.query(question)
        return jsonify({"answer": str(response)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # 0.0.0.0 accepts connections from all devices on the local network
    app.run(host="0.0.0.0", port=5001, debug=False)
```

---

## Step 8 — Find Your Mac's Local IP

```bash
ipconfig getifaddr en0
```

Returns something like `192.168.1.45`. This is your Mac's address on your home network.

**To make it permanent:** Set a DHCP reservation in your router admin page (usually at `192.168.1.1`) under DHCP → Address Reservation. It assigns the same IP to your Mac every time based on its MAC address — so your phone bookmark never breaks.

---

## Step 9 — Open on Any Device

Make sure your phone is on the same WiFi as your Mac, then open any browser:

| Device | URL |
|---|---|
| Mac browser | `http://localhost:5001` |
| iPhone / iPad | `http://192.168.1.45:5001` |
| Any device on WiFi | `http://192.168.1.45:5001` |

You get a clean iMessage-style chat interface. Type a question, tap Send, get an answer with citations.

---

## Daily Usage

Every time you want to use your personal AI, open two Terminal tabs:

```bash
# Tab 1 — keep running
ollama serve

# Tab 2 — start the server
cd ~/personal-ai
source venv/bin/activate
python3 server.py
```

Then open the browser URL on any device.

---

## Updating Your Index

When you have new emails, notes, or documents to add:

1. Place the new files in `my_personal_data/`
2. Run `python3 ingest.py` again — it rebuilds the full index

---

## Mac Performance Settings

These prevent the most common cause of slow or timed-out responses.

**Disable Low Power Mode** — throttles the M5's memory bandwidth and directly slows token generation.
System Settings → Battery → uncheck Low Power Mode.

**Always plug into power** when running the server. macOS throttles CPU/GPU on battery even without Low Power Mode.

**Disable App Nap for Terminal** — stops macOS from throttling Terminal when it's in the background:

```bash
defaults write com.apple.Terminal NSAppSleepDisabled -bool YES
```

---

## Troubleshooting

**`externally-managed-environment` error with pip:**
Forgot to activate the venv. Run `source venv/bin/activate` first, then retry.

**Timeout errors when querying:**
- Confirm Ollama is running: `curl http://localhost:11434`
- Confirm environment variables are set: `echo $OLLAMA_KEEP_ALIVE` (should print `-1`)
- Disable Low Power Mode and plug into power
- The pre-warm block in `server.py` handles cold-start — if you still get timeouts, switch to `qwen2.5:14b` (faster than 35B models)

**`ollama: command not found`:**
Run `brew link ollama` or restart Terminal.

**Phone can't reach the server:**
- Confirm phone and Mac are on the same WiFi
- Confirm `OLLAMA_HOST=0.0.0.0` is set: `echo $OLLAMA_HOST`
- Check firewall: System Settings → Network → Firewall → allow incoming connections on port 5001
- Re-run `ipconfig getifaddr en0` — your IP may have changed since you bookmarked it

**Out of disk space:**
Models live in `~/.ollama/models/`. Remove unused ones:
```bash
ollama rm model-name
```

----

## How RAG Works — Concept Summary

**RAG** (Retrieval-Augmented Generation) solves the problem that AI models can't read your personal files by default.

**Embedding** converts text into a list of numbers (a vector) representing its meaning mathematically. Two pieces of text with similar meanings produce numerically close vectors. This is what enables semantic search — finding relevant content even when it doesn't use your exact keywords. Ask "did anyone mention being stressed about the deadline?" and it finds emails about feeling overwhelmed or anxious, even if the word "stressed" never appears.

**Ingestion phase** (one-time): Files are split into chunks, each chunk is embedded into a vector, all vectors are stored in ChromaDB on your disk.

**Query phase** (every question): Your question is embedded, ChromaDB finds the 3 closest matching chunks, and `qwen2.5:14b` synthesizes an answer from those chunks with citations pointing back to the source files.

---

## Privacy Guarantee

- **No data leaves your Mac.** Ollama runs at `http://localhost:11434` — local only, not the internet.
- **No accounts or API keys.** Models are downloaded once and stored in `~/.ollama/models/`.
- **No usage tracking.** Your questions and documents are never seen by any third party.
- **Works fully offline** after the one-time model download.
- **Network access is local only.** The server is reachable only by devices on your home WiFi — not from the internet.