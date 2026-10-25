"""Application configuration module re-exporting core Settings.

Maintains backward-compatibility and provides a unified config import path.
"""

from app.core.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]
