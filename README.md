# Dilip Agent

A working AI agent in plain Python (no frameworks): tool calling, persistent memory, web research, and a Telegram bot wrapper.

The core loop: user message -> LLM decides -> tool calls -> results fed back -> reply.

## Files
- agent.py: the agent (llm calls, tool loop, 9 tools) + terminal chat
- telegram_bot.py: text your agent on Telegram (long-polling, pure stdlib)
- data/: files the agent saves live here

## Tools included
save_note, get_notes (sqlite memory) - calculator - get_time - web_search (DuckDuckGo, Wikipedia fallback) - fetch_page (read any URL) - save_file, list_files (sandboxed to ./data) - exchange_rate

## Run in terminal
export OPENAI_API_KEY="sk-..."          # or any OpenAI-compatible provider
export OPENAI_BASE_URL="https://openrouter.ai/api/v1"   # optional
export AGENT_MODEL="openai/gpt-4o-mini" # optional
python agent.py

## Run on Telegram
1. Message @BotFather in Telegram -> /newbot -> copy the token
2. export TELEGRAM_BOT_TOKEN="123456:ABC..."
3. python telegram_bot.py
4. Text the bot /start. It replies with your chat id.
5. Security: by default NOBODY can use the bot. Put your chat id in
   export ALLOWED_CHAT_IDS="123456" and restart. Everyone else gets refused.
6. Keep the process running (screen/tmux/systemd on a server, or a
   always-on host like Railway/Render for a live product).

## Growing it
Add a tool = one function + one dict entry in TOOLS. Next ideas:
reminders (sqlite timestamps + cron pings the bot), email via SMTP
(always ask the user first), Google Calendar, voice in/out.
