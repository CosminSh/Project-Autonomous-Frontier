import ipaddress
from urllib.parse import urlparse

from fastapi import HTTPException


LOCAL_HOSTNAMES = {"localhost", "localhost.localdomain"}
MAX_WEBHOOK_URL_LENGTH = 2048


def validate_webhook_url(url: str) -> str:
    cleaned = (url or "").strip()
    if len(cleaned) > MAX_WEBHOOK_URL_LENGTH:
        raise HTTPException(status_code=400, detail="Invalid webhook URL. URL is too long.")
    if any(ord(ch) < 32 for ch in cleaned):
        raise HTTPException(status_code=400, detail="Invalid webhook URL.")

    parsed = urlparse(cleaned)
    if parsed.scheme != "https":
        raise HTTPException(status_code=400, detail="Invalid webhook URL. Must be HTTPS.")
    if not parsed.hostname:
        raise HTTPException(status_code=400, detail="Invalid webhook URL. Missing hostname.")
    if parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail="Invalid webhook URL. Credentials are not allowed.")
    if parsed.port not in (None, 443):
        raise HTTPException(status_code=400, detail="Invalid webhook URL. Only HTTPS port 443 is allowed.")

    host = parsed.hostname.rstrip(".").lower()
    if host in LOCAL_HOSTNAMES or host.endswith(".localhost"):
        raise HTTPException(status_code=400, detail="Invalid webhook URL. Local hosts are not allowed.")

    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return cleaned

    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        raise HTTPException(status_code=400, detail="Invalid webhook URL. Private network targets are not allowed.")

    return cleaned
