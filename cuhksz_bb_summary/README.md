# cuhksz_bb_summary

A small [Playwright](https://playwright.dev/python/) script that logs into **CUHKSZ Blackboard** (`bb.cuhk.edu.cn`), then exports a text summary of:

- **Course Announcements** (stream items on the Course Announcement page)
- **Current Courses** (My Courses widget)
- **Due items** — each unique task taken **only** from **What’s Due**: the **Today**, **Tomorrow**, **This Week**, and **Future** collapsible buckets. Tasks under **What’s Past Due** (**All Items**) are **not** expanded or collected. Each line includes **title**, **course name**, and **due date/time** from the assignment detail page (deduplicated by title + course name).

**Language:** The script targets the **English** Blackboard UI only. Navigation and copy (for example **Notifications Dashboard**, the **What’s Due** bucket labels above, and **Due Date** in the detail panel) are resolved with English-oriented roles and text. Use **English** as the portal language, or adjust `cuhksz_bb_summary.py` to match your locale.

**Home / My Courses:** In Blackboard, open **Home** and configure the **My Courses** module so it lists **only the current term** (current semester’s courses). The script reads whatever appears there for the **Current Courses** section. Due items still come from the **Notifications Dashboard** **What’s Due** module (upcoming buckets), not from Past Due.

Output is written to `course_data_summary.txt` in the **current working directory** (typically this project folder).

---

## Requirements

- Python 3.10+ (recommended)
- Dependencies: see `requirements.txt` (core: `playwright`)

Install Python packages:

```bash
pip install -r requirements.txt
```

Install the browser used by Playwright (Chromium):

```bash
playwright install chromium
```

---

## Configuration

Create **`secrets.json`** next to `cuhksz_bb_summary.py` (this file is listed in `.gitignore` — do not commit it):

```json
{
  "account": "your_student_id_or_username",
  "password": "your_password"
}
```

---

## Usage

From the directory that contains `cuhksz_bb_summary.py` and `secrets.json`:

```bash
python cuhksz_bb_summary.py
```

The script runs **headless** by default and prints progress lines (login, fetching announcements, courses, due deadlines, each due item). On success it writes **`course_data_summary.txt`** and prints total execution time.

To debug with a visible browser, edit `cuhksz_bb_summary.py`: use `chromium.launch(headless=False)` (there is a commented example next to the default `headless=True` line).

---

## Output format

`course_data_summary.txt` contains labeled sections:

1. **Course Announcement** — announcement blocks as plain text
2. **Current Courses** — text from the My Courses area
3. **Due items** — one line per unique due item (from **Today** / **Tomorrow** / **This Week** / **Future** only):
  `title | course_name | due_datetime_from_detail_page`

---

## Limitations

- UI selectors match **this Blackboard instance**; if your institution updates the portal, locators may need updates.
- The same task could theoretically appear in more than one bucket; duplicates are collapsed using **title + course name** so each item is written once.

---

## License

Use at your own risk for personal automation. Keep credentials private.
