"""Generic web building blocks: search and readable page fetching.

No site-specific logic lives here.  ``web_search`` finds candidate pages and
``web_read`` turns one into text; an agent can combine them with
``schedule_task`` to check something (a table, a price, a deal) on a future
date without any booking integration.
"""

import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin

import httpx

from angel_claw.config import settings
from angel_claw.skills.manager import skill
from angel_claw.utils import get_user_root, validate_public_url

SKILL_CONFIG = {
    "fields": [
        {
            "name": "EXA_API_KEY",
            "type": "password",
            "description": "Exa API key (recommended). Free tier at exa.ai.",
        },
        {
            "name": "BRAVE_API_KEY",
            "type": "password",
            "description": "Brave Search API key (fallback when Exa is not set).",
        },
    ]
}

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 AngelClaw/0.17"
)


def _user_field(user_id: str | None, name: str) -> str | None:
    if not user_id:
        return None
    try:
        config_file = get_user_root(user_id) / "skill_config.json"
        if not config_file.exists():
            return None
        with open(config_file) as f:
            config = json.load(f)
        value = (config.get("web") or {}).get("fields", {}).get(name)
        return value or None
    except Exception:
        return None


def _search_keys(user_id: str | None) -> tuple[str | None, str | None]:
    exa = _user_field(user_id, "EXA_API_KEY") or settings.exa_api_key
    brave = _user_field(user_id, "BRAVE_API_KEY") or settings.brave_api_key
    return exa, brave


async def _exa_search(query: str, count: int, api_key: str) -> str:
    payload = {
        "query": query,
        "numResults": count,
        "contents": {
            "text": {"maxCharacters": 1200},
            "highlights": {"numSentences": 2, "highlightsPerUrl": 1},
        },
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://api.exa.ai/search",
            json=payload,
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
        )
    if resp.status_code in (401, 403):
        return "Error: Exa rejected the API key. Update EXA_API_KEY in Skills -> web."
    if resp.status_code != 200:
        return f"Error: Exa search failed with HTTP {resp.status_code}."

    lines = []
    for i, item in enumerate(resp.json().get("results", [])[:count], 1):
        title = (item.get("title") or "Untitled").strip()
        url = item.get("url") or ""
        highlights = " ".join(item.get("highlights") or []).strip()
        snippet = highlights or (item.get("text") or "").strip()[:300]
        lines.append(f"{i}. {title}\n   {url}\n   {snippet}" if snippet else f"{i}. {title}\n   {url}")
    if not lines:
        return f"No web results for '{query}'."
    return f"Web results for '{query}':\n\n" + "\n\n".join(lines)


async def _brave_search(query: str, count: int, api_key: str) -> str:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={
                "X-Subscription-Token": api_key,
                "Accept": "application/json",
            },
            params={"q": query, "count": count},
        )
    if resp.status_code in (401, 403):
        return "Error: Brave rejected the API key. Update BRAVE_API_KEY in Skills -> web."
    if resp.status_code != 200:
        return f"Error: Brave search failed with HTTP {resp.status_code}."

    lines = []
    for i, item in enumerate(
        (resp.json().get("web") or {}).get("results", [])[:count], 1
    ):
        title = (item.get("title") or "Untitled").strip()
        url = item.get("url") or ""
        snippet = (item.get("description") or "").strip()
        lines.append(f"{i}. {title}\n   {url}\n   {snippet}" if snippet else f"{i}. {title}\n   {url}")
    if not lines:
        return f"No web results for '{query}'."
    return f"Web results for '{query}':\n\n" + "\n\n".join(lines)


async def _lightpanda_search(query: str) -> str | None:
    """Keyless search through Lightpanda (Brave/Exa/Tavily/keenable)."""
    try:
        from lightpanda import AsyncBrowser
    except ImportError:
        return None
    try:
        async with AsyncBrowser() as browser:
            async with browser.session() as page:
                text = await page.search(query=query, timeout=15000)
        text = str(text or "").strip()
        return text or None
    except Exception:
        return None


@skill
async def web_search(
    query: str, count: int = 5, user_id: str = None
) -> str:
    """Search the web for current information, deals or local businesses.

    Returns titles, URLs and short snippets. Use web_read on a promising
    result to get the full page. Requires an Exa or Brave API key in
    Skills -> web (or EXA_API_KEY / BRAVE_API_KEY in the environment).
    """
    query = (query or "").strip()
    if not query:
        return "Error: query is required."
    count = max(1, min(int(count or 5), 10))

    exa_key, brave_key = _search_keys(user_id)
    try:
        if exa_key:
            return await _exa_search(query, count, exa_key)
        if brave_key:
            return await _brave_search(query, count, brave_key)
    except httpx.TimeoutException:
        return "Error: web search timed out."
    except Exception as e:
        return f"Error searching the web: {e}"

    # No key: Lightpanda's own search uses a public keyless endpoint.
    results = await _lightpanda_search(query)
    if results:
        return f"Web results for '{query}':\n\n{results}"
    return (
        "Error: web search is unavailable. Add EXA_API_KEY (recommended) "
        "or BRAVE_API_KEY in Skills -> web."
    )


class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "noscript", "svg", "template", "head"}
    _BREAK = {
        "p", "div", "br", "li", "tr", "section", "article", "header",
        "footer", "h1", "h2", "h3", "h4", "h5", "h6", "table", "ul", "ol",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag in self._BREAK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag in self._BREAK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip_depth:
            self.parts.append(data)


def _html_to_text(html: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:
        # Fall back to a crude tag strip for malformed pages.
        return re.sub(r"<[^>]+>", " ", html)
    text = "".join(parser.parts)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


async def _lightpanda_read(url: str) -> str | None:
    """Render with Lightpanda, the bundled headless browser."""
    try:
        from lightpanda import AsyncBrowser
    except ImportError:
        return None
    try:
        async with AsyncBrowser() as browser:
            async with browser.session() as page:
                text = await page.markdown(
                    url=url, max_bytes=200_000, strip={"clutter": True}, timeout=15000
                )
        text = str(text or "").strip()
        return text or None
    except Exception:
        # Some pages time out or use unsupported features; HTTP is a fallback.
        return None


async def _http_read(url: str) -> str:
    headers = {"User-Agent": _USER_AGENT, "Accept": "text/html,application/json,text/plain"}
    async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
        current = url
        for _ in range(4):
            validate_public_url(current)
            resp = await client.get(current, headers=headers)
            if resp.is_redirect:
                location = resp.headers.get("location")
                if not location:
                    raise ValueError("redirect without a location")
                current = urljoin(current, location)
                continue
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "").lower()
            if not any(t in content_type for t in ("html", "text", "json", "xml")):
                raise ValueError(f"unsupported content type: {content_type or 'unknown'}")
            body = resp.content[:2_000_000].decode(resp.encoding or "utf-8", "replace")
            if "html" in content_type:
                return _html_to_text(body)
            return body.strip()
    raise ValueError("too many redirects")


@skill
async def web_read(url: str, max_chars: int = 4000) -> str:
    """Fetch a public web page as readable text.

    Lightpanda renders the page (JavaScript included) and returns markdown;
    a plain HTTP request is used only if the browser fails. Prefer this over
    screenshots for checking menus, deals and availability.
    """
    try:
        validate_public_url(url)
    except ValueError as e:
        return f"Error: {e}"
    max_chars = max(500, min(int(max_chars or 4000), 12000))

    text = await _lightpanda_read(url)
    source = "Lightpanda"
    if not text:
        try:
            text = await _http_read(url)
            source = "HTTP"
        except httpx.TimeoutException:
            return "Error: page fetch timed out."
        except Exception as e:
            return f"Error reading {url}: {e}"

    if not text.strip():
        return f"Error: {url} returned no readable text."
    return f"Content of {url} ({source}):\n\n{text[:max_chars]}"
