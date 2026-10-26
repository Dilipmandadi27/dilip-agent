"""
Telegram wrapper for the mini agent.
Text your agent on Telegram. Pure stdlib (long-polling), no frameworks.

Setup:
1. In Telegram, message @BotFather -> /newbot -> copy the token
2. export TELEGRAM_BOT_TOKEN="123456:ABC..."
3. python telegram_bot.py   (keep it running; Ctrl+C to stop)

Security: ALLOWED_CHAT_IDS is empty by default = nobody can talk to it.
Send your bot /start once, note your chat id from its reply, then put it
in ALLOWED_CHAT_IDS below (or export ALLOWED_CHAT_IDS="123456,789").
"""
import os, json, time, urllib.request

from agent import handle_turn, SYSTEM_PROMPT

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
API = f"https://api.telegram.org/bot{TOKEN}"
RAW = os.environ.get("ALLOWED_CHAT_IDS", "")
ALLOWED = {int(x) for x in RAW.split(",") if x.strip()}
MAX_HISTORY = 30          # messages remembered per chat (context window)
chats = {}                # chat_id -> message history

def tg(method, **payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(f"{API}/{method}", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=70) as r:
        return json.load(r)

def main():
    if not TOKEN:
        print("Set TELEGRAM_BOT_TOKEN first (get one from @BotFather).")
        return
    me = tg("getMe")["result"]
    print(f"bot online: @{me['username']}  allowed chats: {ALLOWED or 'NONE (no one can use it yet)'}")
    offset = None
    while True:
        try:
            params = {"timeout": 50, "allowed_updates": ["message"]}
            if offset:
                params["offset"] = offset
            updates = tg("getUpdates", **params).get("result", [])
        except Exception:
            time.sleep(3)   # network hiccup, keep polling
            continue
        for u in updates:
            offset = u["update_id"] + 1
            msg = u.get("message") or {}
            chat_id = (msg.get("chat") or {}).get("id")
            text = (msg.get("text") or "").strip()
            if not chat_id or not text:
                continue
            if chat_id not in ALLOWED:
                tg("sendMessage", chat_id=chat_id,
                   text=f"This is a private agent. Your chat id is {chat_id} - "
                        f"the owner must add it to ALLOWED_CHAT_IDS.")
                continue
            history = chats.setdefault(chat_id, [{"role": "system", "content": SYSTEM_PROMPT}])
            history.append({"role": "user", "content": text})
            try:
                answer = handle_turn(history)
            except Exception as e:
                answer = f"error: {e}"
            history.append({"role": "assistant", "content": answer})
            del history[1:-MAX_HISTORY]  # trim, keep system prompt
            tg("sendMessage", chat_id=chat_id, text=answer[:4000])

if __name__ == "__main__":
    main()
