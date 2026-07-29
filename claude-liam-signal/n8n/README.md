# n8n workflows

Three importable workflows. Between them the pipeline keeps running with no
session open and nothing on the laptop.

Import each from n8n: **Workflows → Import from File**.

## What they do

**`01-cycle-to-notion-and-telegram.json`** — every 30 minutes, reads the newest
cycle report from GitHub, and when the file has actually changed, parses the
numbers out of it and fans them out: a row into the Notion database, a summary
to Telegram, and a copy into the Drive archive. It remembers the last file hash,
so a report is never sent twice.

**`02-panel-watchdog.json`** — every 15 minutes, checks the panel is answering.
It only messages on a *change* of state, so an hour of downtime produces one
message rather than four. When the panel goes down it also re-triggers the Pages
deploy, which is what would fix it anyway.

**`03-morning-digest.json`** — at 07:23, reads the last cycle and the overnight
parameter search, pulls the verdict out of each, and writes a Gmail **draft**
plus a Telegram message. A draft rather than a send: mail leaving your account
should be your decision.

## Environment variables

Set these in n8n under **Settings → Variables** (or as environment variables on
the n8n host):

| | |
|---|---|
| `TG_TOKEN` | Telegram bot token from @BotFather |
| `TG_CHAT` | Your numeric chat id from @userinfobot |
| `GITHUB_TOKEN` | A token with `workflow` scope, for the watchdog's redeploy |
| `NOTION_TOKEN` | Notion integration token |
| `NOTION_CYCLES_DB` | Id of the "Paper trading cycles" database |
| `DRIVE_FOLDER_ID` | Id of the "Claude Liam Signal" Drive folder |
| `DIGEST_TO` | Where the morning draft is addressed |

The Drive and Gmail nodes also need their own credentials configured in n8n —
those are OAuth connections, not variables.

## What these do not do

They do not decide anything. Thresholds, changes to the engine, and whether a
finding is worth acting on all stay where they were: in the panel's two-hourly
review and in the repository's tests. These workflows move results around and
raise a hand when something stops answering.
