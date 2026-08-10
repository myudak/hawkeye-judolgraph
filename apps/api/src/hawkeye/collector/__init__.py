"""Safe collection primitives for Engine V0."""

from .playwright_collector import BrowserCollector
from .safety import SafetyPolicy, UnsafeUrlError

__all__ = ["BrowserCollector", "SafetyPolicy", "UnsafeUrlError"]
