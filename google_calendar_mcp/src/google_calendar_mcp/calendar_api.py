from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .auth import AuthError, get_credentials


class CalendarApiError(RuntimeError):
    pass


def _http_error_to_message(e: HttpError) -> str:
    try:
        # googleapiclient HttpError has .error_details sometimes, but content is most consistent
        content = e.content.decode("utf-8", errors="replace") if hasattr(e, "content") else str(e)
        return f"Google Calendar API error ({getattr(e, 'status_code', 'unknown')}): {content}"
    except Exception:
        return f"Google Calendar API error: {e}"


@dataclass
class CalendarApi:
    """Thin wrapper around googleapiclient Calendar v3 service."""

    def _service(self):
        creds = get_credentials()
        # cache_discovery=False avoids writing discovery cache files locally
        return build("calendar", "v3", credentials=creds, cache_discovery=False)

    def calendar_list(self) -> dict[str, Any]:
        try:
            svc = self._service()
            items: list[dict[str, Any]] = []
            page_token: Optional[str] = None
            while True:
                resp = (
                    svc.calendarList()
                    .list(pageToken=page_token)
                    .execute()
                )
                items.extend(resp.get("items", []))
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break
            return {"items": items}
        except (AuthError, HttpError) as e:
            raise CalendarApiError(_http_error_to_message(e) if isinstance(e, HttpError) else str(e)) from e

    def calendar_get(self, calendar_id: str) -> dict[str, Any]:
        try:
            svc = self._service()
            return svc.calendars().get(calendarId=calendar_id).execute()
        except (AuthError, HttpError) as e:
            raise CalendarApiError(_http_error_to_message(e) if isinstance(e, HttpError) else str(e)) from e

    def events_list(
        self,
        *,
        calendar_id: str,
        time_min: str,
        time_max: str,
        q: str | None = None,
        max_results: int = 50,
        single_events: bool = True,
        order_by: str = "startTime",
    ) -> dict[str, Any]:
        try:
            svc = self._service()
            resp = (
                svc.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    q=q,
                    maxResults=max_results,
                    singleEvents=single_events,
                    orderBy=order_by if single_events else None,
                )
                .execute()
            )
            return resp
        except (AuthError, HttpError) as e:
            raise CalendarApiError(_http_error_to_message(e) if isinstance(e, HttpError) else str(e)) from e

    def events_get(self, *, calendar_id: str, event_id: str) -> dict[str, Any]:
        try:
            svc = self._service()
            return svc.events().get(calendarId=calendar_id, eventId=event_id).execute()
        except (AuthError, HttpError) as e:
            raise CalendarApiError(_http_error_to_message(e) if isinstance(e, HttpError) else str(e)) from e

    def events_create(self, *, calendar_id: str, event: dict[str, Any]) -> dict[str, Any]:
        try:
            svc = self._service()
            return svc.events().insert(calendarId=calendar_id, body=event).execute()
        except (AuthError, HttpError) as e:
            raise CalendarApiError(_http_error_to_message(e) if isinstance(e, HttpError) else str(e)) from e

    def events_update(self, *, calendar_id: str, event_id: str, event: dict[str, Any]) -> dict[str, Any]:
        try:
            svc = self._service()
            return (
                svc.events()
                .update(calendarId=calendar_id, eventId=event_id, body=event)
                .execute()
            )
        except (AuthError, HttpError) as e:
            raise CalendarApiError(_http_error_to_message(e) if isinstance(e, HttpError) else str(e)) from e

    def events_patch(self, *, calendar_id: str, event_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        try:
            svc = self._service()
            return (
                svc.events()
                .patch(calendarId=calendar_id, eventId=event_id, body=patch)
                .execute()
            )
        except (AuthError, HttpError) as e:
            raise CalendarApiError(_http_error_to_message(e) if isinstance(e, HttpError) else str(e)) from e

    def events_delete(self, *, calendar_id: str, event_id: str) -> dict[str, Any]:
        try:
            svc = self._service()
            svc.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            return {"deleted": True}
        except (AuthError, HttpError) as e:
            raise CalendarApiError(_http_error_to_message(e) if isinstance(e, HttpError) else str(e)) from e

    def events_quick_add(self, *, calendar_id: str, text: str) -> dict[str, Any]:
        try:
            svc = self._service()
            return svc.events().quickAdd(calendarId=calendar_id, text=text).execute()
        except (AuthError, HttpError) as e:
            raise CalendarApiError(_http_error_to_message(e) if isinstance(e, HttpError) else str(e)) from e

    def freebusy_query(
        self,
        *,
        time_min: str,
        time_max: str,
        items: Iterable[dict[str, str]],
        time_zone: str | None = None,
    ) -> dict[str, Any]:
        try:
            svc = self._service()
            body: dict[str, Any] = {"timeMin": time_min, "timeMax": time_max, "items": list(items)}
            if time_zone:
                body["timeZone"] = time_zone
            return svc.freebusy().query(body=body).execute()
        except (AuthError, HttpError) as e:
            raise CalendarApiError(_http_error_to_message(e) if isinstance(e, HttpError) else str(e)) from e

