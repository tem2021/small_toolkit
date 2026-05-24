# Google Calendar MCP (for Cursor)

This project is a **local MCP server** (stdio) that exposes **Google Calendar** tools to Cursor via the official **MCP Python SDK** (`mcp.server.fastmcp.FastMCP`).

## What you get

Tools exposed to Cursor:

- `calendar_list`: list calendars you can access
- `calendar_get`: get calendar metadata
- `events_list`: list events in a time range
- `events_get`: get event by ID
- `events_create`: create an event (full Google event resource body)
- `events_update`: replace event (full update)
- `events_patch`: patch event (partial update, best for chat)
- `events_delete`: delete event
- `events_quick_add`: quick add using natural language
- `freebusy_query`: query busy blocks for one or more calendars

All time inputs must be **RFC3339 / ISO8601** strings, for example:

- `2026-04-15T09:00:00+08:00`
- `2026-04-15T01:00:00Z`

## Security notes (important)

- Do **not** commit OAuth secrets or tokens.
- This repo includes a `.gitignore` that ignores:
  - `client_secret*.json`
  - token files like `token.json`
- Set `GOOGLE_OAUTH_CLIENT_SECRET_PATH` to point to your local client secret JSON.

## How auth works (OAuth user flow)

This server uses a **user OAuth** flow:

- On first tool call, if you have no cached token, it opens your browser for Google authorization.
- It stores the resulting token at:
  - default: `~/.config/google_calendar_mcp/token.json`
  - override with `GOOGLE_OAUTH_TOKEN_PATH`
- It refreshes tokens automatically when expired (using refresh token).

Required scope by default:

- `https://www.googleapis.com/auth/calendar`

Override scopes (comma-separated) with `GOOGLE_OAUTH_SCOPES`.

## Setup (pyenv recommended)

### 1) Create a Python environment

Example using pyenv:

```bash
pyenv install 3.12.3
pyenv virtualenv 3.12.3 google-calendar-mcp
pyenv local google-calendar-mcp
python -V
```

### 2) Install the server

From this directory (`proj/google_calendar_mcp/`):

```bash
python -m pip install -U pip
python -m pip install -e .
```

## Configure Cursor to use this MCP server (stdio)

Cursor supports configuring MCP servers via `mcp.json` (recommended) or the Settings UI. The official docs are at [Cursor MCP docs](https://cursor.com/docs/mcp).

### Example configuration

#### Option A: Project config (recommended for this repo)

Create `.cursor/mcp.json` in this project.

#### Option B: Global config (available in all projects)

Create `~/.cursor/mcp.json`.

#### STDIO server entry

For a local stdio server, Cursor expects `type: "stdio"` plus `command` / `args` / `env` (and optionally `envFile`).

```json
{
  "mcpServers": {
    "google-calendar-mcp": {
      "type": "stdio",
      "command": "/absolute/path/to/python",
      "args": ["-m", "google_calendar_mcp.server"],
      "env": {
        "GOOGLE_OAUTH_CLIENT_SECRET_PATH": "/absolute/path/to/client_secret_...json"
      }
    }
  }
}
```

Notes:

- `command` should be the Python executable from your pyenv environment (or venv).
- `GOOGLE_OAUTH_CLIENT_SECRET_PATH` must point to the OAuth client secret JSON you downloaded from Google Cloud.
- Cursor supports config interpolation like `${userHome}` and `${workspaceFolder}` in `command`, `args`, and `env` values (see docs).

## First run / authorization

After Cursor starts the server, trigger any tool (e.g. `calendar_list`). If no token exists yet, your browser will open and you will:

1. Select your Google account
2. Approve access
3. See a success page

Then tool calls will work normally.

If you are on a headless machine (no browser), you can:

- run the server locally with a browser once to generate `token.json`
- copy the token to the target machine and set `GOOGLE_OAUTH_TOKEN_PATH`

## Example prompts to use in Cursor

- “List my calendars.”
- “Show events on my primary calendar between `2026-04-15T00:00:00+08:00` and `2026-04-16T00:00:00+08:00`.”
- “Create a meeting tomorrow 2–3pm titled ‘Project sync’ on my primary calendar.”
- “Move the event with id `...` to start at `2026-04-16T10:00:00+08:00` and end at `2026-04-16T11:00:00+08:00`.”
- “When am I free this week? Check busy blocks for my primary calendar.”

## Implementation notes (for maintainers)

- MCP server entry point: `src/google_calendar_mcp/server.py`
- OAuth/token handling: `src/google_calendar_mcp/auth.py`
- Calendar API wrapper: `src/google_calendar_mcp/calendar_api.py`

## Troubleshooting

- **Missing client secret path**
  - Set `GOOGLE_OAUTH_CLIENT_SECRET_PATH` to your downloaded client secret JSON.
- **Scope/permission errors**
  - Delete the cached token file and re-authorize.
  - (Or set `GOOGLE_OAUTH_TOKEN_PATH` to a different file.)
- **Time format errors**
  - Ensure `time_min` / `time_max` are RFC3339 strings with timezone, e.g. `...+08:00` or `...Z`.

