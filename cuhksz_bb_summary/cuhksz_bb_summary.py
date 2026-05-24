import json
import re
import time
from pathlib import Path
from playwright.sync_api import Locator, Page, Playwright, sync_playwright

def squeeze(s: str) -> str:
    return " ".join(s.split())


# What's Due (#dueView) buckets from Blackboard Nautilus (see notification HTML).
# "All Items" under What's Past Due (#pastDueView) is intentionally excluded.
DUE_VIEW_BUCKET_HEADER = re.compile(r"^(Today|Tomorrow|This Week|Future)(\s|\(|$)")


def expand_due_view_blocks(page: Page) -> None:
    """Expand Today / Tomorrow / This Week / Future under #dueView. Do not open Past Due 'All Items'."""
    page.locator("#dueView").wait_for(state="visible", timeout=20000)
    headers = page.locator("#dueView").get_by_role("button", name=DUE_VIEW_BUCKET_HEADER)
    for i in range(headers.count()):
        h = headers.nth(i)
        h.wait_for(state="attached", timeout=20000)
        if (h.get_attribute("aria-expanded") or "").lower() != "true":
            h.click()


def whats_due_bucket_rows(page: Page) -> Locator:
    """
    Task rows under ul.itemGroups for What's Due time buckets only (Today, Tomorrow,
    This Week, Future). Excludes What's Past Due (All Items).
    """
    blocks = page.locator("#dueView ul.blockGroups > li").filter(
        has=page.get_by_role("button", name=DUE_VIEW_BUCKET_HEADER)
    )
    return blocks.locator("ul.itemGroups > li")


def open_notifications_dashboard(page: Page, dashboard_url: str | None = None) -> str:
    """
    Navigate to Notifications Dashboard and ensure #dueView (What's Due) is ready.

    - If dashboard_url is provided, use a direct navigation (works from detail pages).
    - Otherwise, click the "Notifications Dashboard" tab and return the resolved URL.
    """
    if dashboard_url:
        page.goto(dashboard_url, wait_until="domcontentloaded")
    else:
        page.get_by_role("link", name="Notifications Dashboard").click()
    expand_due_view_blocks(page)
    return page.url


def run(playwright: Playwright) -> None:

    secrets = json.loads(Path("secrets.json").read_text())
    account = secrets["account"]
    password = secrets["password"]

    # browser = playwright.chromium.launch(headless=False)
    browser = playwright.chromium.launch(headless=True)

    context = browser.new_context(
        locale="en-HK", 
        timezone_id="Asia/Hong_Kong",
        viewport={"width": 1280, "height": 720},
    )

    page = context.new_page()

    print("\r\x1b[K", end="", flush=True)
    print("Logging in...")
    page.goto("https://bb.cuhk.edu.cn/")
    page.get_by_role("button", name="LOGIN").click()
    page.get_by_role("textbox", name="User Account").click()
    page.get_by_role("textbox", name="User Account").fill(account)
    page.get_by_role("button", name="下一步 Next").click()
    page.get_by_role("textbox", name="Password").fill(password)
    page.get_by_role("button", name="登 录 Login").click()
    page.get_by_role("button", name="OK").click()
    page.locator("#global-nav-link").click() 
    page.locator("#AlertsOnMyBb_____AlertsTool").click() 
    page.locator('iframe[name="mybbCanvas"]').content_frame.get_by_role("link", name="Course Announcement").click()

    print("Fetching course announcements...")
    items = page.frame_locator('iframe[name="mybbCanvas"]').locator('div.stream_item')
    items.first.wait_for(state="visible", timeout=20000)
    all_texts = items.all_inner_texts()

    with open("course_data_summary.txt", "w", encoding="utf-8") as f:

        # -- section: course announcement --- 
        f.write("=== SECTION: Course Announcement === \n\n")
        for i, text in enumerate(all_texts, 1):
            clean_text = "\n".join([line.strip() for line in text.splitlines() if line.strip()])
            f.write(f"--- annoucement #{i} ---\n{clean_text}\n\n" + "="*40 + "\n\n")
        f.write("=" * 80 + "\n\n")

        page.get_by_role("link", name="Home", exact=True).click()
        print("Fetching current courses...")
        my_courses = page.locator("#My_Courses_Tools")

        # -- section: current courses --
        f.write("=== SECTION: Current Courses === \n\n")
        f.write(my_courses.inner_text())
        f.write("\n\n" + "=" * 80 + "\n\n")

        # -- section: due items (title | course | due on detail page) ---
        print("Fetching due deadlines (DDL)...")
        dashboard_url = open_notifications_dashboard(page)

        f.write("=== SECTION: Due items === \n\n")

        due_rows = whats_due_bucket_rows(page)
        title_sel = 'a[href="javascript:void(0)"][onclick*="actionSelected"]'

        # Collect due items by visible text (title + course). Blackboard may regenerate
        # internal actionSelected ids on refresh, so we avoid persisting those ids.
        due_items: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        n = due_rows.count()
        for i in range(n):
            row = due_rows.nth(i)
            title = squeeze(row.locator(title_sel).inner_text())
            course = squeeze(row.locator("div.course > a").inner_text())
            key = (title, course)
            if key in seen:
                continue
            seen.add(key)
            due_items.append({"title": title, "course": course})

        total_due = len(due_items)
        for idx, meta in enumerate(due_items):
            print(f"Entering due item {idx + 1}/{total_due}: {meta['title']}")
            if idx > 0:
                open_notifications_dashboard(page, dashboard_url)

            # Re-locate the due row in the current DOM using (title, course), then click title.
            row = (
                whats_due_bucket_rows(page)
                .filter(has_text=meta["title"])
                .filter(has_text=meta["course"])
                .first
            )
            row.locator(title_sel).first.click()
            page.locator("#metadata").wait_for(state="visible", timeout=20000)
            due_text = squeeze(
                page.locator("#metadata .metaSection")
                .filter(has_text="Due Date")
                .locator(".metaField")
                .first.inner_text()
            )
            f.write(f"{meta['title']} | {meta['course']} | {due_text}\n")

        f.write("\n\n" + "=" * 80 + "\n\n")

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    start_time = time.time() 
    run(playwright)
    print(
        f"Total Execution Time: {time.time() - start_time:.2f} seconds"
    )

