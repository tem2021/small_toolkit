from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from .calendar_api import CalendarApi, CalendarApiError


mcp = FastMCP(
    "Google Calendar MCP",
    instructions=(
        "Tools for reading and managing Google Calendar via OAuth user credentials. "
        "Times must be RFC3339 / ISO8601 strings, e.g. 2026-04-15T09:00:00+08:00 or 2026-04-15T01:00:00Z."
    ),
)

api = CalendarApi()

def _require_rfc3339_hint(field: str) -> str:
    return (
        f"Invalid or missing `{field}`. Expected RFC3339 / ISO8601 string like "
        "2026-04-15T09:00:00+08:00 or 2026-04-15T01:00:00Z."
    )


def _ok(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data}


def _err(message: str) -> dict[str, Any]:
    return {"ok": False, "error": message}


@mcp.tool()
def calendar_list() -> dict[str, Any]:
    """List calendars visible to the authenticated user."""
    try:
        return _ok(api.calendar_list())
    except CalendarApiError as e:
        return _err(str(e))


@mcp.tool()
def calendar_get(calendar_id: str) -> dict[str, Any]:
    """Get calendar metadata."""
    try:
        return _ok(api.calendar_get(calendar_id))
    except CalendarApiError as e:
        return _err(str(e))


@mcp.tool()
def events_list(
    calendar_id: str,
    time_min: str,
    time_max: str,
    q: Optional[str] = None,
    max_results: int = 50,
    single_events: bool = True,
    order_by: str = "startTime",
) -> dict[str, Any]:
    """List events in a time range. time_min/time_max must be RFC3339 strings."""
    if not time_min:
        return _err(_require_rfc3339_hint("time_min"))
    if not time_max:
        return _err(_require_rfc3339_hint("time_max"))
    try:
        return _ok(
            api.events_list(
                calendar_id=calendar_id,
                time_min=time_min,
                time_max=time_max,
                q=q,
                max_results=max_results,
                single_events=single_events,
                order_by=order_by,
            )
        )
    except CalendarApiError as e:
        return _err(str(e))


@mcp.tool()
def events_get(calendar_id: str, event_id: str) -> dict[str, Any]:
    """Get a single event by ID."""
    try:
        return _ok(api.events_get(calendar_id=calendar_id, event_id=event_id))
    except CalendarApiError as e:
        return _err(str(e))


@mcp.tool()
def events_create(calendar_id: str, event: dict[str, Any]) -> dict[str, Any]:
    """Create an event. 'event' is the Google Calendar API event resource body."""
    try:
        return _ok(api.events_create(calendar_id=calendar_id, event=event))
    except CalendarApiError as e:
        return _err(str(e))


@mcp.tool()
def events_update(calendar_id: str, event_id: str, event: dict[str, Any]) -> dict[str, Any]:
    """Replace an event (full update)."""
    try:
        return _ok(api.events_update(calendar_id=calendar_id, event_id=event_id, event=event))
    except CalendarApiError as e:
        return _err(str(e))


@mcp.tool()
def events_patch(calendar_id: str, event_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Patch an event (partial update)."""
    try:
        return _ok(api.events_patch(calendar_id=calendar_id, event_id=event_id, patch=patch))
    except CalendarApiError as e:
        return _err(str(e))


@mcp.tool()
def events_delete(calendar_id: str, event_id: str) -> dict[str, Any]:
    """Delete an event."""
    try:
        return _ok(api.events_delete(calendar_id=calendar_id, event_id=event_id))
    except CalendarApiError as e:
        return _err(str(e))


@mcp.tool()
def events_quick_add(calendar_id: str, text: str) -> dict[str, Any]:
    """Quick add an event from natural language text."""
    try:
        return _ok(api.events_quick_add(calendar_id=calendar_id, text=text))
    except CalendarApiError as e:
        return _err(str(e))


@mcp.tool()
def freebusy_query(
    time_min: str,
    time_max: str,
    calendar_ids: list[str],
    time_zone: Optional[str] = None,
) -> dict[str, Any]:
    """Query busy blocks for calendars within a time range."""
    if not time_min:
        return _err(_require_rfc3339_hint("time_min"))
    if not time_max:
        return _err(_require_rfc3339_hint("time_max"))
    if not calendar_ids:
        return _err("calendar_ids must be a non-empty list of calendar IDs.")
    try:
        items = [{"id": cid} for cid in calendar_ids]
        return _ok(api.freebusy_query(time_min=time_min, time_max=time_max, items=items, time_zone=time_zone))
    except CalendarApiError as e:
        return _err(str(e))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

