"""
virustotal.py — VirusTotal v3 API client.

Docs: https://docs.virustotal.com/reference/url-info /
      https://docs.virustotal.com/reference/scan-url /
      https://docs.virustotal.com/reference/analysis

Flow:
  1. Look up the URL directly via GET /urls/{id} (id = base64url(url), no
     padding). If VirusTotal already has a completed report, this returns it
     immediately with no separate "submit" step.
  2. Otherwise POST /urls to queue a new scan, then poll GET
     /analyses/{analysis_id} until it reports status == "completed".

Every outbound request goes through the shared AsyncRateLimiter so the bot
stays under VirusTotal's free-tier caps (4 req/min, 500 req/day) even with
several users scanning at once.
"""
import asyncio
import base64
import logging

import httpx

from common import credentials_store

from .base import ProviderError, RateLimitError, ScanResult, ThreatIntelProvider

logger = logging.getLogger("urlwarden.virustotal")

BASE_URL = "https://www.virustotal.com/api/v3"
POLL_INTERVAL_SECONDS = 3
MAX_POLL_ATTEMPTS = 10


def _url_id(url: str) -> str:
    return base64.urlsafe_b64encode(url.encode("utf-8")).decode("utf-8").rstrip("=")


def _verdict_from_stats(stats: dict) -> str:
    if stats.get("malicious", 0) > 0:
        return "malicious"
    if stats.get("suspicious", 0) > 0:
        return "suspicious"
    return "safe"


class VirusTotalProvider(ThreatIntelProvider):
    name = "VirusTotal"

    def __init__(self, rate_limiter, timeout_seconds: float = 20.0):
        self._rate_limiter = rate_limiter
        self._timeout = timeout_seconds

    def _headers(self) -> dict:
        # Read fresh each call so a key change saved in the dashboard applies
        # to the next scan immediately, without restarting the bot.
        return {"x-apikey": credentials_store.get_virustotal_key()}

    async def scan_url(self, url: str) -> ScanResult:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            stats = await self._get_existing_report(client, url)
            if stats is None:
                analysis_id = await self._submit_url(client, url)
                stats = await self._poll_analysis(client, analysis_id)
            return ScanResult(
                verdict=_verdict_from_stats(stats),
                malicious=stats.get("malicious", 0),
                suspicious=stats.get("suspicious", 0),
                harmless=stats.get("harmless", 0),
                undetected=stats.get("undetected", 0),
                total=sum(stats.values()),
                permalink=f"https://www.virustotal.com/gui/url/{_url_id(url)}",
                provider=self.name,
            )

    async def _get_existing_report(self, client: httpx.AsyncClient, url: str):
        await self._rate_limiter.acquire()
        resp = await self._request(client, "GET", f"{BASE_URL}/urls/{_url_id(url)}")

        if resp.status_code == 404:
            return None
        self._raise_for_status(resp)
        attributes = resp.json()["data"]["attributes"]
        # Only reuse a report that has actually finished analyzing; otherwise re-submit.
        return attributes.get("last_analysis_stats") or None

    async def _submit_url(self, client: httpx.AsyncClient, url: str) -> str:
        await self._rate_limiter.acquire()
        resp = await self._request(client, "POST", f"{BASE_URL}/urls", data={"url": url})
        self._raise_for_status(resp)
        return resp.json()["data"]["id"]

    async def _poll_analysis(self, client: httpx.AsyncClient, analysis_id: str) -> dict:
        for _attempt in range(MAX_POLL_ATTEMPTS):
            await self._rate_limiter.acquire()
            resp = await self._request(client, "GET", f"{BASE_URL}/analyses/{analysis_id}")
            self._raise_for_status(resp)
            attributes = resp.json()["data"]["attributes"]
            if attributes.get("status") == "completed":
                return attributes["stats"]
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
        raise ProviderError("VirusTotal scan did not finish in time, please try again shortly")

    async def _request(self, client: httpx.AsyncClient, method: str, url: str, **kwargs) -> httpx.Response:
        try:
            return await client.request(method, url, headers=self._headers(), **kwargs)
        except httpx.TimeoutException as exc:
            raise ProviderError("VirusTotal request timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"VirusTotal request failed: {exc}") from exc

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.status_code == 429:
            raise RateLimitError("VirusTotal rate limit reached")
        if resp.status_code == 401:
            raise ProviderError("VirusTotal rejected the API key — check it in the admin dashboard")
        if resp.status_code >= 400:
            raise ProviderError(f"VirusTotal error (HTTP {resp.status_code})")
