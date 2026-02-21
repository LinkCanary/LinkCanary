"""LinkCanary - A link health checker tool."""

__version__ = "0.3"

from .webhook_dispatcher import WebhookDispatcher, WebhookProvider

__all__ = ["WebhookDispatcher", "WebhookProvider"]
