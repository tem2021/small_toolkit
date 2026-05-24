import os
import datetime
import copy
import sys
import subprocess
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SCOPES = ['https://www.googleapis.com/auth/calendar']
DEFAULT_MAX_RESULTS = 20


# handle google calendar api authorization, return api client
def get_calendar_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token: 
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                raise FileNotFoundError(
                    "Fail to find 'credentials.json' in current folder. "
                    "Please download it from google cloud -> auth -> client."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            print("\r\x1b[K", end="", flush=True)
            print("Write token to 'token.json'", end="", flush=True)
    
    return build('calendar', 'v3', credentials=creds)


# return normal string from datetime
# typ = "start" | "end"
def datetime_to_str(event: dict, typ: str):
    dt = event.get(typ, {})
    if not dt: return ""
    return dt.get("dateTime") or dt.get("date", "")


# return the well organized recurrence string
def recurrence_to_str(event: dict):
    recur = event.get("recurrence", [])
    if not recur: return ""
    return ', '.join(recur)


# better format event
def format_event(event: dict):
    event = copy.deepcopy(event)
    if "start" in event: event["start"] = datetime_to_str(event, "start")
    if "end" in event: event["end"] = datetime_to_str(event, "end")
    if "recurrence" in event: event["recurrence"] = recurrence_to_str(event)
    return event


# better format comparsion event
def format_compared_event(old_event: dict, new_event: dict):
    old_event = format_event(copy.deepcopy(old_event))
    new_event = format_event(copy.deepcopy(new_event))
    for key, val in new_event.items():
        old_event[key] = f"(old) {old_event.get(key,'None')} -> (new) {val}"
    return old_event


# show event information
def show_event(event: dict):
    print(f"Event ID    : {event.get('id', '')}")
    print(f"Event Title : {event.get('summary', '')}")
    print(f"Start Time  : {event.get('start', '')}")
    print(f"End Time    : {event.get('end', '')}")

    if event.get("recurrence"):
        print(f"Recurrence  : {event.get('recurrence')}")
    if event.get("description"):
        print(f"Description : {event.get('description')}")
    if event.get("location"):
        print(f"Location    : {event.get('location')}")


# get calendar event based on calendar_id and event_id
def get_calendar_event(calendar_id: str, event_id: str):
    try:
        service = get_calendar_service()
        return service.events().get(calendarId=calendar_id, 
                                     eventId=event_id).execute()
    except HttpError as e:
        print(f"Faults happened when querying the calendar event "
              f"(ID: {event_id}): {e}")
        return {}


# list all calendars and their corresponding ID
def list_user_calendars():
    try: 
        service = get_calendar_service()
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get('items',[])

        if not calendars:
            print('No calendar found')
            return []

        cleaned_calendars = []
        for cal in calendars:
            cleaned_calendar = {
                "id": cal.get("id"),
                "summary": cal.get("summary", ""),
                "primary": 1 if cal.get("primary") else 0
            }
            cleaned_calendars.append(cleaned_calendar)

        return cleaned_calendars
    except HttpError as e:
        print(f"Faults happened when getting the list of calendars: {e}")
        return []


# get calendar timezone based on account: e.g. Asia/Shanghai
def get_calendar_timezone():
    try: 
        service = get_calendar_service()
        return service.settings().get(setting='timezone').execute().get('value')
    except HttpError as e:
        print(f"Faults happened when querying calendar timezone: {e} ")
        return "UTC"


# get calendar name based on calendar_id
def get_calendar_name(calendar_id: str):
    try:
        service = get_calendar_service()
        calendar = service.calendarList().get(calendarId=calendar_id).execute()
        return calendar.get("summary", "")
    except HttpError as e:
        print(f"Faults happened when querying the calendar name "
              f"(ID: {calendar_id}): {e}")
        return ""


# query calendar events in a specific time range or via text keyword
# result: largest number of return events
# time format example: 2026-05-28T23:59:59Z
def query_calendar(start_time: str = None, end_time: str = None,
                   calendar_id: str = 'all',
                   max_results: int = DEFAULT_MAX_RESULTS, 
                   text_query: str = None):
    try: 
        service = get_calendar_service()

        # aquire the users calendars
        calendars = list_user_calendars()
        calendar_map = {cal["id"]: cal["summary"] for cal in calendars}
        if not calendar_map: calendar_map["primary"] = "Primary"

        # determine the target ids
        if calendar_id == "all": target_ids = list(calendar_maps.keys())
        else: target_ids = [cid.strip() for cid in calendar_id.split(',')]

        all_events = []
        for cid in target_ids:
            params = {
                "calendarId": calendar_id,
                "maxResults": max_results,
                "singleEvents": True,
                "orderBy": 'startTime'
            }

            if start_time: params["timeMin"] = start_time
            if end_time:   params["timeMax"] = end_time
            if text_query: params["q"] = text_query

            try:
                events_result = service.events().list(**params).execute()
                events = events_result.get('items', [])

                for event in events:
                    cleaned_event = {
                        "id": event.get("id"),
                        "summary": event.get("summary", ""),
                        "start": datetime_to_str(event, "start"),
                        "end": datetime_to_str(event, "end"),
                        "description": event.get("description", ""),
                        "location": event.get("location", ""),
                        "status": event.get("status"),
                        "calendar": calendar_map.get(cid, cid)
                    }
                    all_events.append(cleaned_event)
            except HttpError: continue

        all_events.sort(key=lambda x: x.get('start',''))
        return all_events
    
    except HttpError as e:
        print(f"Faults happened when QUERY Google Calendar API {e}")
        return []


# get the specific instances of recurring event
def get_recurring_instances(master_event_id: str, calendar_id: str = 'primary',
                            max_results: int = DEFAULT_MAX_RESULTS):
    try: 
        service = get_calendar_service()
        instances_result = service.events().instances(
                                calendarId=calendar_id,
                                eventId=master_event_id,
                                maxResults=max_results).execute()

        instances = instances_result.get('items', [])
        cleaned_instances = []
        for inst in instances:
            cleaned_instances.append({
                "instance_id": inst.get("id"),
                "summary": inst.get("summary", ""),
                "start": datetime_to_str(inst, "start"),
                "end": datetime_to_str(inst, "end")
            })
        return cleaned_instances
    except HttpError as e:
        print(f"Faults happened when fetching recurring instances: {e}")
        return []


# split the recurring event at a specific date, and update the future instances
# split_date_str: 20260704
def split_recurring_event(calendar_id: str, master_id: str, 
                          split_date_str:str, new_event_body: dict):
    try:
        service = get_calendar_service()
        master_event = service.events().get(calendarId=calendar_id, 
                                            eventId=master_id).execute()
        recurrence = master_event.get('recurrence', [])
        if not recurrence:
            print("[!] The event is not a recurring event. Cannot split.")
            return {"status": "error", "message": "not a recurring event"}
        
        print(f"\nRequesting SPLIT of recurring event (include this event):")
        print(f"[Split Effective] {split_date_str}")

        # show the detailed information
        show_event(format_compared_event(master_event, new_event_body))

        confirm = input("\nDo you want to split this series? (y/n): "
                        ).strip().lower()

        if confirm != 'y':
            return {"status": "cancelled", 
                    "message": "operation cancelled by the user."}

        split_date = datetime.datetime.strptime(split_date_str, "%Y%m%d")
        until_date = split_date - datetime.timedelta(days=1)
        until_str  = until_date.strftime("%Y%m%dT235959Z")   # 23:59:59

        new_recurrence = [] 
        for rrule in recurrence:    # either ends by UNTIL or COUNT
            clean_rrule = ";".join([p for p in rrule.split(";") if (
                                       not p.startswith("UNTIL") and
                                       not p.startswith("COUNT")
                                 )])
            new_recurrence.append(f"{clean_rrule};UNTIL={until_str}")
        
        master_event['recurrence'] = new_recurrence

        service.events().update(calendarId=calendar_id, eventId=master_id,
                                body=master_event).execute()
        print("-> Successfully truncated the original series.")
        
        result = service.events().insert(calendarId=calendar_id, 
                                         body=new_event_body).execute()
        print("-> Successfully created the new recurring series.")

        return {
            "status": "success",
            "truncated_master_id": master_id,
            "new_master_id": result.get("id"),
            "event": result
        }

    except HttpError as e:
        print(f"Faults happened when splitting recurring event: {e}")
        return {"status": "error", "message": str(e)}


# support operation: insert, update, patch, delete & manual lock
# action: insert/update/patch/delete
# event_body: {"summary": "title", "start": {"dateTime": }, "end":...}
def mutate_calendar_event(action:str, calendar_id: str = 'primary', 
                          event_id: str = None, event_body: dict = None):
    calendar_name = get_calendar_name(calendar_id)
    if not calendar_name: 
        return {"status": "error", 
                "message": f"invalid calendar_id: {calendar_id}"}

    # check the validation of args
    if action not in ['insert', 'update', 'patch', 'delete']:
        return {"status": "error", "message": f"invalid action: {action}"}

    if action in ['update', 'patch', 'delete'] and not event_id:
        return {"status": "error", 
                "message": f"please offer event_id when doing {action}"}

    if action in ['insert', 'update', 'patch'] and not event_body:
        return {"status": "error",
                "message": f"please offer event_body when doing {action}"}

    # manually confirm
    print(f"\nModify {calendar_name} with {action.upper()} action...")

    if action == 'insert': shown_body = format_event(event_body)

    if action in ['patch', 'delete', 'update']:
        shown_body = get_calendar_event(calendar_id, event_id)

        if not shown_body: return {"status": "error", 
                                   "message": f"invalid event_id: {event_id}"}

        if action == 'delete': shown_body = format_event(shown_body)
        else: shown_body = format_compared_event(shown_body, event_body)

        if "recurringEventId" in shown_body:
            print("[!] This target is a SINGLE INSTANCE of a recurring event.")

    # show the detailed information
    show_event(shown_body)

    confirm = input(f"\nDo you want to modify the {calendar_name}? (y/n): "
                    ).strip().lower()

    if confirm != 'y': return  {"status": "cancelled", 
                                "message": "operation cancelled by the user."}
    
    try:
        service = get_calendar_service()

        if action == "insert":
            result = service.events().insert(calendarId=calendar_id,
                                             body=event_body).execute()
            return {"status": "success",
                    "action": "insert",
                    "event_id": result.get("id"),
                    "event": result}

        elif action == "update":
            result = service.events().update(calendarId=calendar_id,
                                             eventId=event_id,
                                             body=event_body).execute()
            return {"status": "success",
                    "action": "update",
                    "event_id": event_id,
                    "event": result}

        elif action == "patch":
            result = service.events().patch(calendarId=calendar_id,
                                            eventId=event_id,
                                            body=event_body).execute()
            return {"status": "success",
                    "action": "patch",
                    "event_id": event_id,
                    "event": result}

        elif action == "delete":
            service.events().delete(calendarId=calendar_id,
                                    eventId=event_id).execute()
            return {"status": "success",
                    "action": "delete",
                    "event_id": event_id}

    except HttpError as e:
        print(f"Faults happened when {action.upper()} Google Calendar API: {e}")
        return {"status": "error", "message": str(e)}


# update the BB summary 
# NOTICE: remember to change the PATH of the cuhksz_bb_summary/ python 
#         binary file if you use different virtual environment
def fetch_school_course_summary():
    current_file_path   = os.path.abspath(__file__)
    base_dir           = os.path.dirname(os.path.dirname(current_file_path))
    bb_dir              = os.path.join(base_dir, "cuhksz_bb_summary")
    script_path         = os.path.join(bb_dir, "cuhksz_bb_sumary.py")
    txt_path            = os.path.join(bb_dir, "course_data_summary.txt")

    if not os.path.exists(bb_dir): 
        return {"status":  "error",
                "message": f"sibling directory not found: {bb_dir}"}

    # python binary file for cuhksz_bb_summary.py
    py_exe = "/home/andytan/.pyenv/versions/webBrowser/bin/python"

    print("\r\x1b[K", end="", flush=True)
    print(f"Executing cuhksz_bb_summary.py", end="", flush=True)
    subprocess.run([py_exe, "cuhksz_bb_summary.py"], cwd=bb_dir,
                    capture_output=True, text=True, check=True)

    with open(txt_path, "r", encoding="utf-8") as f: content = f.read().strip()
    return {"status": "success", "summary": content}

