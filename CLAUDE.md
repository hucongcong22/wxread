# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python script that automates reading time tracking for WeChat Read (微信读书). The script simulates reading sessions by making authenticated API requests to the WeChat Read web interface.

## Architecture

Three-file structure:
- **config.py** - Configuration and credentials: reads `WXREAD_CURL_BASH` from env or uses hardcoded headers/cookies, contains book/chapter IDs, signing logic
- **main.py** - Core automation: signs requests (SHA256 + custom hash), handles cookie renewal via `wr_skey`, rate limits requests (30s intervals)
- **push.py** - Notification module: supports PushPlus, WxPusher, Telegram, ServerChan for completion alerts

## Running

```bash
# Run directly
python main.py

# Run with environment variables
READ_NUM=40 PUSH_METHOD=pushplus PUSHPLUS_TOKEN=xxx python main.py

# Docker build & run
docker build -t wxread . && docker run -d --name wxread -v $(pwd)/logs:/app/logs wxread
```

## Key Configuration

| Variable | Description |
|----------|-------------|
| `READ_NUM` | Reading count (default 40 = 20 min) |
| `PUSH_METHOD` | pushplus/wxpusher/telegram/serverchan |
| `WXREAD_CURL_BASH` | Curl command from captured `/web/book/read` request |

## Request Signing

The `sg` field uses SHA256: `sha256(ts + rn + KEY)` where KEY is hardcoded in main.py.
The `s` field uses a custom hash algorithm (see `cal_hash()` in main.py:16).
