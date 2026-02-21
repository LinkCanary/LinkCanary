"""LinkCanary - A link health checker tool."""

__version__ = "0.3"

from .exporters import ExportFormat, ReportExporter, detect_format
from .patterns import URLPatternMatcher, PRESET_PATTERNS
from .robots import RobotsComplianceChecker, RobotsTxtParser
from .webhook_dispatcher import WebhookDispatcher, WebhookProvider

__all__ = [
    "ExportFormat",
    "ReportExporter",
    "URLPatternMatcher",
    "PRESET_PATTERNS",
    "RobotsComplianceChecker",
    "RobotsTxtParser",
    "detect_format",
    "WebhookDispatcher",
    "WebhookProvider",
]
