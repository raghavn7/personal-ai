import os

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template_string, request
from flask_httpauth import HTTPBasicAuth
import httpx
import keyring
from llama_index.core import PromptTemplate, StorageContext, load_index_from_storage
from llama_index.core import Settings
from llama_index.core.postprocessor import LLMRerank
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
import markdown
import ollama as ollama_client
from werkzeug.security import check_password_hash, generate_password_hash


# ── app + auth ────────────────────────────────────────────────
app = Flask(__name__)
auth = HTTPBasicAuth()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_DIR = os.path.join(BASE_DIR, "my_index")

_username = keyring.get_password("personal-ai", "ai_username")
_password = keyring.get_password("personal-ai", "ai_password")

if not _username or not _password:
    raise RuntimeError("Credentials not found in Keychain. Run setup commands first.")

USERS = {
    _username: generate_password_hash(_password)
}

@auth.verify_password
def verify_password(username, password):
    if username in USERS and check_password_hash(USERS[username], password):
        return username

@auth.error_handler
def auth_error(status):
    return "Access denied.", status

# ── model setup ───────────────────────────────────────────────
timeout = httpx.Timeout(connect=30.0, read=900.0, write=30.0, pool=30.0)

Settings.llm = Ollama(
    model="qwen2.5:14b",
    request_timeout=900.0,
    http_client=httpx.Client(timeout=timeout),
)
Settings.embed_model = OllamaEmbedding(
    model_name="nomic-embed-text",
    http_client=httpx.Client(timeout=120.0),
)

# ── warm up ───────────────────────────────────────────────────
print("Warming up model (may take 30-60 seconds on first run)...")
ollama_client.chat(
    model="qwen2.5:14b",
    messages=[{"role": "user", "content": "hi"}],
    options={"num_predict": 1}
)

# ── load index ────────────────────────────────────────────────
print("Loading index...")
storage_context = StorageContext.from_defaults(persist_dir=INDEX_DIR)
index = load_index_from_storage(storage_context)

# ── custom prompt ─────────────────────────────────────────────
qa_prompt = PromptTemplate("""
You are a personal AI assistant with access to the user's private emails,
messages, and notes. Answer the question using ONLY the context provided below.
Be specific — include names, dates, and direct details from the context.
If the answer is not in the context, say "I couldn't find that in your data."
Do not make anything up.

Context:
-----------
{context_str}
-----------

Question: {query_str}

Answer:
""")

# ── reranker + query engine ───────────────────────────────────
reranker = LLMRerank(
    choice_batch_size=5,
    top_n=5,
)

query_engine = index.as_query_engine(
    similarity_top_k=10,
    node_postprocessors=[reranker],
    response_mode="compact",
)
query_engine.update_prompts({"response_synthesizer:text_qa_template": qa_prompt})

print("Ready.\n")

# ── chat UI ───────────────────────────────────────────────────
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

  const creds = btoa("{{ username }}:{{ password }}");

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
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Basic ' + creds
        },
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

# ── routes ────────────────────────────────────────────────────
@app.route("/")
@auth.login_required
def home():
    return render_template_string(
        HTML,
        username=auth.current_user(),
        password=request.authorization.password
    )

@app.route("/query", methods=["POST"])
@auth.login_required
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

@app.route("/readme")
@auth.login_required
def readme():
    readme_path = os.path.join(BASE_DIR, "README.md")
    content = open(readme_path).read()
    html = markdown.markdown(content, extensions=["tables", "fenced_code"])
    return f"""
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
      body {{ max-width: 800px; margin: 40px auto; font-family: -apple-system,
              sans-serif; padding: 0 20px; line-height: 1.6; color: #1c1c1e; }}
      code {{ background: #f5f5f5; padding: 2px 6px; border-radius: 4px; font-size: 14px; }}
      pre  {{ background: #f5f5f5; padding: 16px; border-radius: 8px; overflow-x: auto; }}
      table {{ border-collapse: collapse; width: 100%; }}
      td, th {{ border: 1px solid #ddd; padding: 8px 12px; }}
      th {{ background: #f5f5f5; }}
      h1, h2, h3 {{ margin-top: 1.5em; }}
      hr {{ border: none; border-top: 1px solid #e5e5ea; margin: 2em 0; }}
      a {{ color: #007AFF; }}
    </style>
    {html}
    """

# ── start ─────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)