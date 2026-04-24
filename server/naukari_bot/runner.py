"""
Reusable Naukri profile-update runner.

Pure function `run_naukri_update(RunConfig)` that logs in to Naukri, uploads a
resume PDF, and bumps the resume headline. No environment-variable coupling,
no sys.exit, no SMTP — callers (CLI or web app) handle those concerns.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

from playwright.async_api import (
    BrowserContext,
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
    # JSON (str) output of Playwright's `context.storage_state()` from the
    # previous successful run. Restores cookies/localStorage so the browser
    # resumes the last Naukri session without another credential login.
    initial_storage_state_json: Optional[str] = None
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
    finished_at: datetime = field(default_factory=_utcnow)
    # The latest known-good `storage_state` JSON captured right after a
    # successful login. Callers should persist this (encrypted) so subsequent
    # runs can reuse it. None when no fresh session was ever established.
    final_storage_state_json: Optional[str] = None


async def run_naukri_update(cfg: RunConfig) -> RunResult:
    """Top-level entry. Retries on failure; returns a structured RunResult."""
    last_error: Optional[str] = None
    artifacts: list[str] = []
    # Populated by `_upload_resume_once` as soon as login succeeds — even if a
    # later step fails we still want to persist the fresh cookies so the next
    # run can resume.
    state_sink: list[str] = []

    for attempt in range(1, cfg.max_retries + 1):
        log.info("Attempt %d", attempt)
        try:
            headline = await _upload_resume_once(cfg, state_sink)
            return RunResult(
                success=True,
                headline=headline,
                attempts=attempt,
                artifacts=artifacts,
                final_storage_state_json=state_sink[-1] if state_sink else None,
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
        final_storage_state_json=state_sink[-1] if state_sink else None,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _dump_debug_artifacts(page: Page, prefix: str, artifacts_dir: str) -> list[str]:
    out: list[str] = []
    try:
        # Normalise to an absolute path so the dump location doesn't depend on
        # whatever cwd uvicorn / cron happened to start from.
        artifacts_dir = os.path.abspath(artifacts_dir)
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


async def _upload_resume_once(
    cfg: RunConfig,
    state_sink: list[str],
) -> str:
    async with async_playwright() as p:
        headless = not cfg.headed
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
        ]
        browser = await p.chromium.launch(headless=headless, args=launch_args)
        new_context_kwargs: dict[str, Any] = {
            "viewport": {"width": 1280, "height": 720},
            "locale": "en-IN",
            "timezone_id": "Asia/Kolkata",
        }
        initial_state = _parse_storage_state(cfg.initial_storage_state_json)
        if initial_state is not None:
            log.info("Restoring Naukri session from stored storage_state")
            new_context_kwargs["storage_state"] = initial_state
        context: BrowserContext = await browser.new_context(**new_context_kwargs)
        page = await context.new_page()

        try:
            await _ensure_logged_in(page, cfg)

            # Capture the fresh, known-good session cookies as soon as we're
            # logged in — even if the resume/headline steps fail later, the
            # caller can still persist this so the next run skips login.
            await _capture_storage_state(context, state_sink)

            await page.click("text=Update resume")
            # In-memory FilePayload: the `name` field is exactly what the
            # browser sends to Naukri in `Content-Disposition: filename=...`.
            # Using a path-on-disk would leak the tempfile's random basename
            # (e.g. `resume_abc123.pdf`) instead of the canonical dated name.
            await page.set_input_files(
                "input[type='file']",
                files=[
                    {
                        "name": cfg.resume_filename,
                        "mimeType": "application/pdf",
                        "buffer": cfg.resume_bytes,
                    }
                ],
            )
            await page.wait_for_timeout(5000)
            log.info("Resume uploaded to Naukri as %r", cfg.resume_filename)

            await page.goto("https://www.naukri.com/mnjuser/profile", timeout=60000)
            await page.wait_for_load_state("domcontentloaded", timeout=30000)
            await page.wait_for_selector("text=Resume headline", timeout=20000)
            await page.wait_for_timeout(2000)

            headline = await _update_resume_headline(page)
            # Re-capture after the headline edit so any tokens refreshed during
            # the update get persisted too.
            await _capture_storage_state(context, state_sink)
            return headline
        finally:
            await browser.close()


def _parse_storage_state(raw: Optional[str]) -> Optional[dict[str, Any]]:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError) as e:
        log.warning("Stored storage_state is not valid JSON — ignoring (%s)", e)
        return None
    if not isinstance(parsed, dict):
        log.warning("Stored storage_state has unexpected shape — ignoring")
        return None
    return parsed


async def _capture_storage_state(context: BrowserContext, sink: list[str]) -> None:
    """Dump the current storage_state into `sink` so the caller can persist it."""
    try:
        state = await context.storage_state()
        sink.append(json.dumps(state))
    except Exception as e:  # noqa: BLE001
        log.warning("Failed to capture storage_state: %s", e)
