"""
base.py — Provider-agnostic interface for threat-intelligence backends.

VirusTotal is the only implementation today, but scan_url()'s signature and
the ScanResult shape are deliberately generic so a second provider (Google
Safe Browsing, urlscan.io, ...) can be added later purely by implementing
ThreatIntelProvider — no changes needed in handlers.py or main.py beyond
picking which provider(s) to instantiate.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ScanResult:
    verdict: str  # "safe" | "suspicious" | "malicious"
    malicious: int
    suspicious: int
    harmless: int
    undetected: int
    total: int
    permalink: Optional[str] = None
    provider: str = ""


class ProviderError(Exception):
    """Any provider failure that should surface as a friendly chat message."""


class RateLimitError(ProviderError):
    """The provider's own rate limit was hit (e.g. HTTP 429)."""


class ThreatIntelProvider(ABC):
    name: str

    @abstractmethod
    async def scan_url(self, url: str) -> ScanResult:
        """Submit/query url and return a normalized ScanResult, or raise ProviderError."""
