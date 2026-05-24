import os
import sys
import json
import datetime
import calendar_tools as cal
from openai import OpenAI
from rich.console import Console
from rich.markdown import Markdown


# deal with the terminal echo for unix-like system 
try: import termios
except ImportError: termios = None


# better input for unix-like system
try: import readline
except ImportError: readline = None


# max turns for ReAct reasoning loop
DEFAULT_MAX_TURNS = 15


# active models: deepseek-v4-flash / deepseek-v4-pro
MODEL_NAME = "deepseek-v4-flash"


# initiallize an output console
console = Console()


# define the interactive tools
INTERACTIVE_TOOLS = {
    "mutate_calendar_event",
    "split_recurring_event"
}

# configure DeepSeek client
if os.path.exists("DEEPSEEK_API_KEY"):
    with open("DEEPSEEK_API_KEY", "r") as f:
        DEEPSEEK_KEY = f.read().strip()
else:
    raise SystemExit("No API key found, exiting automatically")

client = OpenAI(
    api_key=DEEPSEEK_KEY,
    base_url="https://api.deepseek.com"
)


# Map JSON schema function names to real callable Python functions
AVAILABLE_TOOLS = {
    "list_user_calendars":          cal.list_user_calendars,
    "get_calendar_name":            cal.get_calendar_name,
    "get_calendar_timezone":        cal.get_calendar_timezone,
    "query_calendar":               cal.query_calendar,
    "get_calendar_event":           cal.get_calendar_event,
    "mutate_calendar_event":        cal.mutate_calendar_event,
    "get_recurring_instances":      cal.get_recurring_instances,
    "split_recurring_event":        cal.split_recurring_event,
    "fetch_school_course_summary":  cal.fetch_school_course_summary
}


# deal with the input echo
def disable_input_echo():
    if not termios: return None
    try:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        new_settings = termios.tcgetattr(fd)
        # turn of the ECHO flag in terminal local modes
        new_settings[3] = new_settings[3] & ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSADRAIN, new_settings)
        return old_settings
    except Exception: return None


def restore_input_echo(old_settings):
    if not termios or not old_settings: return 
    try:
        fd = sys.stdin.fileno()
        termios.tcflush(fd, termios.TCIFLUSH)
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except Exception: return


# load tools specification from the local JSON file
def load_tools_specification():
    with open("tools_specification.json", "r") as f:
        return json.load(f)


# run the ReAct reasoning loop for a single turn of conversation
# def run_calendar_agent(user_prompt: str):
def run_react_cycle(messages: list, tools_spec: list):
    for turn in range(DEFAULT_MAX_TURNS):
        old_term_settings = disable_input_echo()

        print("\r\x1b[K", end="", flush=True)
        print("\rAgent thinking...", end="", flush=True)

        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=tools_spec,
                tool_choice="auto"
            )
        finally: restore_input_echo(old_term_settings)

        response_msg = response.choices[0].message
        messages.append(response_msg)

        tool_calls = response_msg.tool_calls
        if not tool_calls:
            print("\r\x1b[K", end="", flush=True)
            console.print(Markdown(response_msg.content))
            break

        print("\r\x1b[K", end="", flush=True)
        for tool_call in tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)

            is_silent_tool = (func_name not in INTERACTIVE_TOOLS)
            tool_term_settings = None
            if is_silent_tool: tool_term_settings = disable_input_echo()

            print("\r\x1b[K", end="", flush=True)
            print(f"Function executing: {func_name}...", end="", flush=True)

            try:
                if func_name in AVAILABLE_TOOLS:
                    try: result = AVAILABLE_TOOLS[func_name](**func_args)
                    except Exception as e:
                        result = {"status": "error", "message": str(e)}
                else:
                    result = {
                        "status": "error",
                        "message": f"Tool '{func_name}' not found."
                    }
            finally: 
                if is_silent_tool: restore_input_echo(tool_term_settings)
            
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": func_name,
                "content": json.dumps(result)
            })

    # check if running out all turns without break
    else:
        print("\nReasoning loop terminated due to turn limit.")

    return messages


if __name__ == "__main__":
    tools_spec = load_tools_specification()     # load function definition
    messages = []                               # messages context
    print("TYPE 'exit/quit/q' TO END THE SESSION.")

    while 1:
        # inject the exact current time 
        now_local = datetime.datetime.now().astimezone()
        now_str = now_local.isoformat()
        weekday_str = now_local.strftime("%A")

        # system prompt
        system_prompt = (
            "You are an intelligent Calendar Agent managing Google Calendar.\n"
            f"Today is {weekday_str}, ISO datetime is: {now_str}.\n\n"
            "RULES OF ENGAGEMENT:\n"
            "1. NO BLIND MUTATIONS: Before executing any write/mutate actions "
            "(insert, patch, update, delete), you must ALWAYS call query_calendar "
            "first to inspect the current state and prevent duplication.\n"
            "2. TIMEZONE INTEGRITY: Always query default timezone using "
            "get_calendar_timezone before scheduling/formatting dates.\n"
            "3. RECURRING EVENTS STRATEGY:\n"
            "   - To modify/delete ALL occurrences: Target the Master ID.\n"
            "   - To modify/delete ONLY THIS occurrence: Target the Instance ID "
            "(use get_recurring_instances first to resolve the specific date).\n"
            "   - To modify/delete THIS AND FUTURE occurrences: Use "
            "split_recurring_event.\n"
            "4. Be concise. Output reasoning step-by-step.\n"
            "5. FUZZY & SEMANTIC MATCHING: Users may misspell names or only remember "
            "vague details (e.g., 'someone surnamed Yang' or 'toothache' instead of "
            "'dentist'). Always perform case-insensitive and semantic matching. "
            "If a search is vague, you must:\n"
            "   - Query multiple keyword variants (e.g. both '杨' and 'Yang').\n"
            "   - Query a broader time range to inspect and filter candidates "
            "semantically in your brain.\n"
            "   - Gracefully suggest the closest match to the user "
            "(e.g., 'I found \"Snoopy\'s Birthday\" instead of \"snoppy\", is that "
            "what you meant?').\n"
        )

        # dynamically update the system prompt
        if not messages: messages.append({"role": "system", 
                                          "content": system_prompt})
        else: messages[0]["content"] = system_prompt

        try: user_query = input("> ").strip()
        except (KeyboardInterrupt, EOFError):        # Ctrl+C, Ctrl+D
            raise SystemExit("")

        if not user_query: continue
        if user_query.lower() in ["exit", "quit", "q"]:
            raise SystemExit("")

        messages.append({"role": "user", "content": user_query})
        messages = run_react_cycle(messages, tools_spec)
        print()

