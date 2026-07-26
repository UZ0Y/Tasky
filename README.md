# Tasky

Tasky is an independent Discord accountability bot designed to help you manage tasks, track goals, and get proactive coaching through direct messages. It also supports concurrent access from external web dashboards (Flask, Django, etc.) without conflicts, thanks to a carefully configured SQLite setup.

## Features

- **Natural language understanding** – No rigid command syntax. Just tell the bot what you need, and it uses an LLM to classify your intent, extract the task, and start a confirmation flow.
- **Two interaction modes**:
  - *Reactive* – Short, direct replies to conversational messages.
  - *Proactive* – Thoughtful check‑ins that recap your progress.
- **Powered by Gemini** – Integrates with Google’s Gemini models, with built‑in exponential backoff and retry logic to handle rate limits and temporary network issues.
- **Production‑ready SQLite concurrency** – Uses Write‑Ahead Logging (WAL) and timeout buffers, allowing the Discord bot and a separate web framework to read and write to the same database safely.
- **Persistent state** – Pending task confirmations and queued messages are stored directly in the database, so nothing is lost if the bot restarts.

## Project Structure

```
Tasky/
├── src/
│   ├── bot/
│   │   └── main.py                 # Discord client, logging, and main execution loop
│   ├── shared/                     # Shared modules used by both the bot and external tools
│   │   ├── config.py               # Global configuration, path setup, and startup validation
│   │   ├── database.py             # SQLite schema with WAL mode, tables for tasks, pending confirmations, and message history
│   │   ├── prompts.py              # System prompts for reactive and proactive modes
│   │   └── response_generator.py   # Intent classification and Gemini API calls with retry logic
│   └── tester_tools/               # Standalone scripts for testing and queueing
│       ├── terminal_sender.py      # Tool to queue proactive messages from the command line
│       └── test_gemini.py          # Quick test to verify Gemini API connectivity
├── .env                            # Environment variables (token, API key, model)
├── requirements.txt                # Python dependencies
└── README.md
```

## Setup

1. **Clone the repository** and navigate into the project folder:
   ```bash
   git clone <repo-url>
   cd Tasky
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Create a `.env` file** in the root directory with the following variables:
   ```
   TOKEN=your_discord_bot_token_here
   GEMINI_API_KEY=your_gemini_api_key_here
   GEMINI_MODEL=gemini-2.5-flash
   ```
   The bot will exit on startup if any of these are missing.

4. **(Optional) Test the Gemini API**:
   ```bash
   python -m src.tester_tools.test_gemini
   ```

5. **Run the bot**:
   ```bash
   python -m src.bot.main
   ```

## Web Dashboard Integration

Tasky is built to work alongside web applications. Because the database is configured with SQLite WAL mode, you can connect a Flask or Django app to the same `Tasks.db` file without locking issues.

- Insert messages into the `PROACTIVE_QUEUE` table from your web backend – the bot will automatically pick them up and send them to Discord.
- Update task status columns in the `TASKS` table – the bot will immediately reflect those changes.

This makes it easy to build a custom dashboard for managing tasks, viewing history, or triggering proactive reminders.