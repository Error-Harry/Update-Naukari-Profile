"""
Reusable Naukri profile-update runner.

Pure function `run_naukri_update(RunConfig)` that logs in to Naukri, uploads a
resume PDF, and bumps the resume headline. No environment-variable coupling,
no sys.exit, no SMTP — callers (CLI or web app) handle those concerns.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from playwright.async_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class RunConfig:
    naukri_email: str
    naukri_password: str
    resume_bytes: bytes
    resume_filename: str
    user_data_dir: Optional[str] = None
    headed: bool = True
    max_retries: int = 2
    artifacts_dir: str = "artifacts"


@dataclass
class RunResult:
    success: bool
    headline: Optional[str] = None
    error: Optional[str] = None
    attempts: int = 0
    artifacts: list[str] = field(default_factory=list)
    finished_at: datetime = field(default_factory=datetime.utcnow)


async def run_naukri_update(cfg: RunConfig) -> RunResult:
    """Top-level entry. Retries on failure; returns a structured RunResult."""
    last_error: Optional[str] = None
    artifacts: list[str] = []
    headline: Optional[str] = None

    with tempfile.NamedTemporaryFile(
        prefix="resume_", suffix=_safe_suffix(cfg.resume_filename), delete=False
    ) as tmp:
        tmp.write(cfg.resume_bytes)
        resume_path = tmp.name

    try:
        for attempt in range(1, cfg.max_retries + 1):
            log.info("Attempt %d", attempt)
            try:
                headline = await _upload_resume_once(cfg, resume_path)
                return RunResult(
                    success=True,
                    headline=headline,
                    attempts=attempt,
                    artifacts=artifacts,
                )
            except Exception as e:  # noqa: BLE001
                last_error = str(e)
                log.error("Attempt %d failed: %s", attempt, e)
                await asyncio.sleep(5)
        return RunResult(
            success=False,
            error=last_error,
            attempts=cfg.max_retries,
            artifacts=artifacts,
        )
    finally:
        try:
            os.remove(resume_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_suffix(filename: str) -> str:
    _, ext = os.path.splitext(filename or "")
    return ext if ext else ".pdf"


async def _dump_debug_artifacts(page: Page, prefix: str, artifacts_dir: str) -> list[str]:
    out: list[str] = []
    try:
        os.makedirs(artifacts_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = os.path.join(artifacts_dir, f"{prefix}_{ts}")
        await page.screenshot(path=f"{base}.png", full_page=True)
        out.append(f"{base}.png")
        html = await page.content()
        with open(f"{base}.html", "w", encoding="utf-8") as f:
            f.write(html)
        out.append(f"{base}.html")
        with open(f"{base}.txt", "w", encoding="utf-8") as f:
            f.write(f"url={page.url}\n")
            try:
                f.write(f"title={await page.title()}\n")
            except Exception:
                pass
        out.append(f"{base}.txt")
        log.info("Saved debug artifacts: %s(.png/.html/.txt)", base)
    except Exception as e:  # noqa: BLE001
        log.info("Debug artifact dump failed: %s", e)
    return out


async def _wait_for_any(page: Page, *, urls, selectors, timeout_ms: int) -> None:
    tasks = []
    for u in urls:
        tasks.append(
            asyncio.create_task(
                page.wait_for_url(u, wait_until="domcontentloaded", timeout=timeout_ms)
            )
        )
    for s in selectors:
        tasks.append(
            asyncio.create_task(
                page.locator(s).first.wait_for(state="visible", timeout=timeout_ms)
            )
        )
    done, pending = await asyncio.wait(
        tasks, timeout=timeout_ms / 1000, return_when=asyncio.FIRST_COMPLETED
    )
    for p in pending:
        p.cancel()
    if not done:
        raise PlaywrightTimeoutError(
            f"Timeout {timeout_ms}ms waiting for any of urls={urls} selectors={selectors}"
        )
    await list(done)[0]


async def _login(page: Page, cfg: RunConfig) -> None:
    await page.goto(
        "https://www.naukri.com/nlogin/login",
        wait_until="domcontentloaded",
        timeout=60000,
    )
    log.info("Login page: url=%r title=%r", page.url, await page.title())

    user = page.locator("#usernameField, #emailTxt, input[name='USERNAME']").first
    await user.wait_for(state="visible", timeout=45000)

    pwd_new = page.locator("#passwordField")
    if await pwd_new.is_visible():
        await page.locator("#usernameField").fill(cfg.naukri_email)
        await pwd_new.fill(cfg.naukri_password)
        await page.locator("button[type='submit']").first.click()
    else:
        await page.locator("#emailTxt, input[name='USERNAME']").first.fill(cfg.naukri_email)
        await page.locator("#pwd1").fill(cfg.naukri_password)
        await page.locator("#sbtLog[name='Login']").first.click()

    try:
        await _wait_for_any(
            page,
            urls=["**/mnjuser/homepage**", "**/mnjuser/profile**", "**/mnjuser/**"],
            selectors=["a[href*='logout' i]", "a[href*='mnjuser/profile' i]"],
            timeout_ms=60000,
        )
    except Exception:
        await _dump_debug_artifacts(page, "login_post_submit", cfg.artifacts_dir)
        raise
    log.info("Login successful — redirected (or logged-in UI detected)")

    await page.wait_for_timeout(2000)
    try:
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(1000)
    except Exception:
        pass


async def _session_valid_on_profile(page: Page) -> bool:
    if "nlogin" in page.url.lower():
        return False
    try:
        await page.wait_for_selector("text=Resume", timeout=15000)
        return True
    except PlaywrightTimeoutError:
        return False


async def _ensure_logged_in(page: Page, cfg: RunConfig) -> None:
    await page.goto(
        "https://www.naukri.com/mnjuser/profile",
        wait_until="domcontentloaded",
        timeout=60000,
    )
    if await _session_valid_on_profile(page):
        log.info("Existing Naukri session is still valid — skipping credential login.")
        return
    log.info("No usable session — performing login.")
    await _login(page, cfg)
    await page.goto("https://www.naukri.com/mnjuser/profile", timeout=60000)
    await page.wait_for_selector("text=Resume", timeout=20000)


async def _update_resume_headline(page: Page) -> str:
    log.info("Updating resume headline...")
    TEXTAREA = "#resumeHeadlineTxt"
    SAVE_BTN = ".form-actions button[type='submit']"

    async def scroll_and_open_editor() -> None:
        await page.evaluate(
            "const el=document.querySelector('#lazyResumeHead');"
            "if(el)el.scrollIntoView({behavior:'smooth',block:'center'});"
        )
        await page.wait_for_timeout(2000)
        edit = (
            page.locator(".widgetHead")
            .filter(has_text="Resume headline")
            .locator("span.edit.icon")
        )
        await edit.wait_for(state="visible", timeout=15000)
        await edit.evaluate("n => n.click()")
        await page.wait_for_selector(TEXTAREA, state="visible", timeout=20000)

    async def save_and_close() -> None:
        await page.locator(SAVE_BTN).first.click()
        await page.wait_for_selector(TEXTAREA, state="hidden", timeout=20000)
        await page.wait_for_timeout(1500)

    await scroll_and_open_editor()
    textarea = page.locator(TEXTAREA)
    original = await textarea.input_value()
    log.info("Current headline: %r", original)

    await textarea.fill(original + ".")
    await save_and_close()

    await scroll_and_open_editor()
    await page.locator(TEXTAREA).fill(original)
    await save_and_close()
    log.info("Headline update complete")
    return original


async def _upload_resume_once(cfg: RunConfig, resume_path: str) -> str:
    async with async_playwright() as p:
        headless = not cfg.headed
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
        ]
        browser = None
        context = None
        if cfg.user_data_dir:
            os.makedirs(cfg.user_data_dir, exist_ok=True)
            log.info("Using persistent browser profile at %s", cfg.user_data_dir)
            context = await p.chromium.launch_persistent_context(
                cfg.user_data_dir,
                headless=headless,
                viewport={"width": 1280, "height": 720},
                locale="en-IN",
                timezone_id="Asia/Kolkata",
                args=launch_args,
            )
            page = context.pages[0] if context.pages else await context.new_page()
        else:
            browser = await p.chromium.launch(headless=headless, args=launch_args)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                locale="en-IN",
                timezone_id="Asia/Kolkata",
            )
            page = await context.new_page()

        try:
            await _ensure_logged_in(page, cfg)

            await page.click("text=Update resume")
            await page.set_input_files("input[type='file']", resume_path)
            await page.wait_for_timeout(5000)
            log.info("Resume uploaded")

            await page.goto("https://www.naukri.com/mnjuser/profile", timeout=60000)
            await page.wait_for_load_state("domcontentloaded", timeout=30000)
            await page.wait_for_selector("text=Resume headline", timeout=20000)
            await page.wait_for_timeout(2000)

            headline = await _update_resume_headline(page)
            return headline
        finally:
            if browser:
                await browser.close()
            else:
                assert context is not None
                await context.close()
