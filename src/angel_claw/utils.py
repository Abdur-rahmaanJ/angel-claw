import asyncio
import ipaddress
import os
import re
import socket
from pathlib import Path
from urllib.parse import urlparse
from .config import settings


def safe_filename_part(value: str, fallback: str = "default") -> str:
    """Make a chat session id safe to use as a file name.

    Session ids come from clients, so strip path separators, leading dots and
    anything that could climb out of the per-user directory.
    """
    cleaned = re.sub(r"[^A-Za-z0-9._ -]", "_", str(value or ""))
    cleaned = cleaned.strip(" .")
    return cleaned or fallback

def _validate_public_ip(address: str) -> None:
    ip = ipaddress.ip_address(address.split("%", 1)[0])
    if not ip.is_global:
        raise ValueError("internal addresses are not allowed")


def validate_public_url(url: str) -> str:
    """Only public http(s) URLs: web tools must not reach internal services."""
    parsed = urlparse(url or "")
    if parsed.scheme not in ("http", "https"):
        raise ValueError("only http and https URLs are allowed")
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        raise ValueError("a host is required")
    if host == "localhost" or host.endswith(
        (".localhost", ".local", ".internal", ".home.arpa")
    ):
        raise ValueError("internal hosts are not allowed")
    try:
        _validate_public_ip(host)
    except ValueError as e:
        # ipaddress rejects names; only re-raise for an actual address.
        try:
            ipaddress.ip_address(host.split("%", 1)[0])
        except ValueError:
            return url
        raise e
    return url


async def validate_public_url_resolved(url: str) -> str:
    """Validate a URL and every address its hostname currently resolves to.

    The literal check alone lets a hostname whose DNS record points at a
    loopback or private address reach internal services.
    """
    validate_public_url(url)
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    try:
        ipaddress.ip_address(host.split("%", 1)[0])
        return url
    except ValueError:
        pass

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(
            host, port, type=socket.SOCK_STREAM
        )
    except socket.gaierror as e:
        raise ValueError(f"could not resolve host: {host}") from e
    addresses = {info[4][0] for info in infos}
    if not addresses:
        raise ValueError(f"could not resolve host: {host}")
    for address in addresses:
        _validate_public_ip(address)
    return url


def get_user_root(user_id: str) -> Path:
    """Get the root directory for a specific user's data."""
    root = Path(settings.user_data_root).expanduser()
    user_dir = root / "users" / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        user_dir.chmod(0o700)
    except OSError:
        pass
    return user_dir
