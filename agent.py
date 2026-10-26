"""
Mini AI Agent - a working skeleton you can grow.
The agent loop: user message -> LLM decides -> call tools -> feed results back -> reply.
Run:  set OPENAI_API_KEY / OPENAI_BASE_URL first, then:  python agent.py
"""
import os, json, sqlite3, datetime, urllib.request

API_KEY = os.environ.get("OPENAI_API_KEY", "")
BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
MODEL = os.environ.get("AGENT_MODEL", "gpt-4o-mini")
DB = "memory.db"

# ---------- memory (sqlite, persists between runs) ----------
def db():
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS memories (id INTEGER PRIMARY KEY, text TEXT, created TEXT)")
    return c

def remember(text):
    c = db()
    c.execute("INSERT INTO memories (text, created) VALUES (?, ?)",
              (text, datetime.datetime.now().isoformat()))
    c.commit()
    return f"saved: {text}"

def recall(query=""):
    c = db()
    if query:
        rows = c.execute("SELECT text FROM memories WHERE text LIKE ? ORDER BY id DESC LIMIT 10",
                         (f"%{query}%",)).fetchall()
    else:
        rows = c.execute("SELECT text FROM memories ORDER BY id DESC LIMIT 10").fetchall()
    return rows if rows else ["(no memories yet)"]

# ---------- tool registry: add new tools by adding one dict ----------
def save_note(args):
    return remember(args.get("text", ""))

def get_notes(args):
    return "\n".join(str(r[0]) for r in recall(args.get("query", "")))

def run_calc(args):
    expr = args.get("expression", "")
    allowed = set("0123456789+-*/.() ")
    if not set(expr) <= allowed:
        return "only basic math allowed"
    return str(eval(expr))  # sandboxed to digits/operators above

def now_time(args):
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M %A")

def web_search(args):
    """Search the web via DuckDuckGo Lite (no API key). Falls back to Wikipedia."""
    import urllib.parse, re, json
    q = args.get("query", "")
    if not q:
        return "no query given"
    clean = lambda x: re.sub(r"<[^>]+>", "", x).strip()
    try:
        url = "https://lite.duckduckgo.com/lite/?q=" + urllib.parse.quote(q)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", "ignore")
        rows = re.findall(r"class=.result-link.[^>]*>(.*?)</a>", html, re.S)[:5]
        snips = re.findall(r"class=.result-snippet.(.*?)</td>", html, re.S)[:5]
        out = [f"{n}. {clean(t)}: {' '.join(clean(s).split())[:200]}" for n, (t, s) in enumerate(zip(rows, snips + [""] * 5), 1)]
        if out:
            return "\n".join(out)
    except Exception:
        pass
    try:
        url = ("https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit=3&srsearch="
               + urllib.parse.quote(q))
        req = urllib.request.Request(url, headers={"User-Agent": "mini-agent/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read().decode())
        out = [f"- {clean(x['title'])}: {' '.join(clean(x['snippet']).split())[:180]}" for x in d["query"]["search"]]
        return "Wikipedia results:\n" + "\n".join(out) if out else "no results found"
    except Exception as e:
        return f"search failed: {e}"


def fetch_page(args):
    """Open a webpage and return its readable text, first 3000 characters."""
    import urllib.request, re
    url = args.get("url", "")
    if not url.startswith("http"):
        url = "https://" + url
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", "ignore")
    except Exception as e:
        return f"fetch failed: {e}"
    html = re.sub(r"<(script|style)[^>]*>.*?</\\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:3000] if text else "(empty page)"

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

def save_file(args):
    """Save a file inside ./data only (sandboxed). Args: filename, content"""
    name = args.get("filename", "")
    safe = os.path.basename(name)  # no paths, no dotdot
    if not safe:
        return "no filename given"
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, safe)
    with open(path, "w", encoding="utf-8") as f:
        f.write(args.get("content", ""))
    return f"saved {safe} ({len(args.get('content', ''))} chars)"

def list_files(args):
    """List files saved in ./data."""
    if not os.path.isdir(DATA_DIR):
        return "(no files yet)"
    files = os.listdir(DATA_DIR)
    return "\n".join(files) if files else "(no files yet)"

def exchange_rate(args):
    """Live currency exchange rates via open.er-api.com (no key). Args: from_currency, to_currency"""
    base = (args.get("from_currency") or "USD").upper()[:3]
    target = (args.get("to_currency") or "INR").upper()[:3]
    try:
        with urllib.request.urlopen(f"https://open.er-api.com/v6/latest/{base}", timeout=15) as r:
            d = json.loads(r.read().decode())
        rate = d.get("rates", {}).get(target)
        if rate is None:
            return f"unknown currency pair {base}->{target}"
        return f"1 {base} = {rate} {target} (as of {d.get('time_last_update_utc', '?')})"
    except Exception as e:
        return f"rate check failed: {e}"


TOOLS = {
    "save_note":  {"fn": save_note, "desc": "Save a fact to memory. Args: text",
                   "schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    "get_notes":  {"fn": get_notes, "desc": "Search saved memories. Args: query (optional)",
                   "schema": {"type": "object", "properties": {"query": {"type": "string"}}}},
    "calculator": {"fn": run_calc, "desc": "Do math. Args: expression",
                   "schema": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}},
    "get_time":   {"fn": now_time, "desc": "Current date and time. Args: none",
                   "schema": {"type": "object", "properties": {}}},
    "web_search": {"fn": web_search, "desc": "Search the web for current info. Args: query",
                   "schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    "fetch_page": {"fn": fetch_page, "desc": "Open a URL and return its page text. Use after web_search. Args: url",
                   "schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
    "save_file":  {"fn": save_file, "desc": "Save a text file to the agent's data folder. Args: filename, content",
                   "schema": {"type": "object", "properties": {"filename": {"type": "string"}, "content": {"type": "string"}}, "required": ["filename", "content"]}},
    "list_files": {"fn": list_files, "desc": "List saved files. Args: none",
                   "schema": {"type": "object", "properties": {}}},
    "exchange_rate": {"fn": exchange_rate, "desc": "Live currency conversion rate. Args: from_currency, to_currency (3-letter codes)",
                   "schema": {"type": "object", "properties": {"from_currency": {"type": "string"}, "to_currency": {"type": "string"}}, "required": ["from_currency", "to_currency"]}},
}

def llm(messages):
    """One call to any OpenAI-compatible API (OpenAI, OpenRouter, Groq, local...)."""
    body = json.dumps({
        "model": MODEL,
        "messages": messages,
        "tools": [{"type": "function", "function": {"name": n, "description": t["desc"], "parameters": t["schema"]}} for n, t in TOOLS.items()],
    }).encode()
    req = urllib.request.Request(f"{BASE_URL}/chat/completions", data=body,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["choices"][0]["message"]

SYSTEM_PROMPT = ("You are a helpful personal agent. Use tools when they help. "
                 "Save important user facts with save_note. Be concise.")

def handle_turn(messages):
    """One full agent turn: append the answer (and any tool calls) to messages.
    Reuses the same tool loop whether input came from terminal or Telegram."""
    for _ in range(5):  # max 5 tool round-trips per turn
        reply = llm(messages)
        if reply.get("tool_calls"):
            messages.append(reply)
            for tc in reply["tool_calls"]:
                name = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"] or "{}")
                print(f"  [tool] {name}({args})")
                result = TOOLS[name]["fn"](args)
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": str(result)})
        else:
            messages.append({"role": "assistant", "content": reply["content"]})
            return reply["content"]
    return "I got stuck in a tool loop there, try rephrasing."

def run_agent():
    if not API_KEY:
        print("Set OPENAI_API_KEY (and optionally OPENAI_BASE_URL, AGENT_MODEL) first.")
        return
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    print(f"agent online ({MODEL}). type 'quit' to exit.")
    while True:
        user = input("\nyou: ").strip()
        if user.lower() in ("quit", "exit"):
            break
        messages.append({"role": "user", "content": user})
        answer = handle_turn(messages)
        print(f"agent: {answer}")

if __name__ == "__main__":
    run_agent()
