"""Browser automation backed by Lightpanda (bundled with the `lightpanda` wheel)."""

import asyncio
import os

from angel_claw.skills.manager import skill
from angel_claw.utils import validate_public_url

_browser = None
_page = None
_loop = None


def _screenshot_path(path: str) -> str:
    """Keep screenshots in the user data dir, never arbitrary filesystem paths."""
    from angel_claw.config import settings

    out_dir = settings.data_dir / "screenshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = os.path.basename(path or "screenshot.png")
    if not name:
        name = "screenshot.png"
    return str(out_dir / name)


async def _get_page():
    global _browser, _page, _loop
    loop = asyncio.get_running_loop()
    if _page is None or _loop is not loop:
        from lightpanda import AsyncBrowser

        _browser = AsyncBrowser()
        await _browser.start()
        _page = await _browser.new_session()
        _loop = loop
    return _page


async def _reset():
    global _browser, _page, _loop
    if _browser is not None:
        try:
            await _browser.close()
        except Exception:
            pass
    _browser = None
    _page = None
    _loop = None


@skill
async def browser_navigate(url: str) -> str:
    """Open a URL in Lightpanda and return the page as readable markdown."""
    try:
        validate_public_url(url)
        page = await _get_page()
        await page.goto(url=url, timeout=15000)
        text = await page.markdown(max_bytes=6000, strip={"clutter": True})
        text = str(text or "").strip()
        return f"Navigated to {url}. Content:\n\n{text[:4000]}"
    except Exception as e:
        return f"Error navigating to {url}: {e}"


@skill
async def browser_click(selector: str) -> str:
    """Click an element (CSS selector) on the current page."""
    try:
        page = await _get_page()
        await page.click(selector=selector)
        return f"Clicked {selector}."
    except Exception as e:
        return f"Error clicking {selector}: {e}"


@skill
async def browser_type(selector: str, text: str) -> str:
    """Fill an input on the current page."""
    try:
        page = await _get_page()
        await page.fill(selector=selector, value=text)
        return f"Filled {selector}."
    except Exception as e:
        return f"Error filling {selector}: {e}"


@skill
async def browser_screenshot(path: str = "screenshot.png") -> str:
    """Save a screenshot of the current page into the user data directory."""
    try:
        page = await _get_page()
        target = _screenshot_path(path)
        await page.screenshot(path=target)
        return f"Screenshot saved to {target}."
    except Exception as e:
        return f"Error taking screenshot: {e}"


@skill
async def browser_close() -> str:
    """Close the browser session."""
    try:
        await _reset()
        return "Browser closed."
    except Exception as e:
        return f"Error closing browser: {e}"
