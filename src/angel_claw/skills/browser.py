from playwright.async_api import async_playwright
import ipaddress
import os
import asyncio
import httpx
from urllib.parse import urlparse
from angel_claw.config import settings
from angel_claw.skills.manager import skill

_browser = None
_page = None
_playwright = None

async def _get_page():
    global _browser, _page, _playwright
    if _page is None:
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(headless=True)
        _page = await _browser.new_page()
    return _page

def _validate_url(url: str) -> None:
    """Only public http(s): the browser must not reach internal services."""
    parsed = urlparse(url or "")
    if parsed.scheme not in ("http", "https"):
        raise ValueError("only http and https URLs are allowed")
    host = (parsed.hostname or "").lower()
    if not host or host == "localhost" or host.endswith(".local"):
        raise ValueError("internal hosts are not allowed")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        raise ValueError("internal addresses are not allowed")


def _screenshot_path(path: str) -> str:
    """Keep screenshots in the user data dir, never arbitrary filesystem paths."""
    from angel_claw.config import settings

    out_dir = settings.data_dir / "screenshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = os.path.basename(path or "screenshot.png")
    if not name:
        name = "screenshot.png"
    return str(out_dir / name)


@skill
async def browser_navigate(url: str) -> str:
    """Navigates to a URL and returns the page text content."""
    try:
        _validate_url(url)
        page = await _get_page()
        await page.goto(url)
        # Instead of raw HTML, return a text summary or accessibility snapshot
        text = await page.inner_text("body")
        return f"Successfully navigated to {url}. Content summary: {text[:1000]}..."
    except Exception as e:
        print(f"DEBUG: Error in browser_navigate: {e}")
        return f"Error navigating to {url}: {e}"

@skill
async def browser_click(selector: str) -> str:
    """Clicks an element on the current page."""
    try:
        page = await _get_page()
        await page.click(selector)
        return f"Successfully clicked {selector}."
    except Exception as e:
        print(f"DEBUG: Error in browser_click: {e}")
        return f"Error clicking {selector}: {e}"

@skill
async def browser_type(selector: str, text: str) -> str:
    """Types text into an input field."""
    try:
        page = await _get_page()
        await page.type(selector, text)
        return f"Successfully typed into {selector}."
    except Exception as e:
        print(f"DEBUG: Error in browser_type: {e}")
        return f"Error typing into {selector}: {e}"

@skill
async def browser_screenshot(path: str = "screenshot.png") -> str:
    """Takes a screenshot of the current page."""
    try:
        page = await _get_page()
        target = _screenshot_path(path)
        await page.screenshot(path=target)
        return f"Screenshot saved to {target}."
    except Exception as e:
        print(f"DEBUG: Error in browser_screenshot: {e}")
        return f"Error taking screenshot: {e}"

@skill
async def browser_search(query: str) -> str:
    """
    Performs a web search using the Brave Search API.
    Requires BRAVE_API_KEY in .env.
    """
    if not settings.brave_api_key:
        return "Error: BRAVE_API_KEY not found in configuration. Please add it to your .env file to use search."

    try:
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {"X-Subscription-Token": settings.brave_api_key, "Accept": "application/json"}
        params = {"q": query, "count": 5}
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code == 401:
                return "Error: Invalid BRAVE_API_KEY. Please check your configuration."
            resp.raise_for_status()
            data = resp.json()
            
        results = []
        if "web" in data and "results" in data["web"]:
            for i, item in enumerate(data["web"]["results"]):
                title = item.get("title", "No Title")
                link = item.get("url", "No Link")
                snippet = item.get("description", "No Snippet")
                results.append(f"{i+1}. {title}\n   Link: {link}\n   Snippet: {snippet}\n")
                
        if not results:
            return f"No results found for '{query}'."
            
        return "Brave Search Results:\n" + "\n".join(results)

    except Exception as e:
        print(f"DEBUG: Error in browser_search: {e}")
        return f"Error searching for '{query}': {e}"

@skill
async def browser_close() -> str:
    """Closes the browser session."""
    global _browser, _page, _playwright
    try:
        if _browser:
            await _browser.close()
        if _playwright:
            await _playwright.stop()
        _browser = None
        _page = None
        _playwright = None
        return "Browser closed."
    except Exception as e:
        print(f"DEBUG: Error in browser_close: {e}")
        return f"Error closing browser: {e}"
