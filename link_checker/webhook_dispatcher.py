"""Webhook dispatcher interface for future platform integrations.

Phase 2 will add support for:
- Webflow API integration
- Framer webhook handlers
- WordPress plugin
- Ghost admin integration
- OAuth flows for any platform

This module provides the interface for registering and dispatching
webhooks to multiple providers.
"""

from typing import Any, Callable, Optional


class WebhookDispatcher:
    """Future home for Webflow/Ghost/WordPress integrations.
    
    Usage (Phase 2):
        dispatcher = WebhookDispatcher()
        dispatcher.register('webflow', WebflowHandler(site_id, secret))
        dispatcher.register('ghost', GhostHandler(api_url, api_key))
        dispatcher.dispatch('link_check_completed', payload)
    """

    def __init__(self):
        self.providers: dict[str, Callable] = {}

    def register(self, provider_name: str, handler: Callable) -> None:
        """Register a webhook provider handler.
        
        Args:
            provider_name: Unique identifier for the provider (e.g., 'webflow', 'ghost')
            handler: Callable that handles webhook delivery for this provider
        """
        self.providers[provider_name] = handler

    def unregister(self, provider_name: str) -> None:
        """Remove a registered provider."""
        self.providers.pop(provider_name, None)

    def dispatch(self, event: str, payload: dict) -> dict[str, tuple[bool, Optional[str]]]:
        """Dispatch an event to all registered providers.
        
        Args:
            event: Event name (e.g., 'link_check_completed', 'crawl_failed')
            payload: Event data dictionary
        
        Returns:
            Dict mapping provider names to (success, error_message) tuples
        
        Note: This is a stub for Phase 2. Currently returns empty dict.
        """
        # To be implemented when we add SaaS hosting
        # Each provider will receive the event and payload,
        # format it appropriately, and deliver via their API
        results = {}
        
        # Phase 2 implementation will look like:
        # for name, handler in self.providers.items():
        #     try:
        #         success, error = handler.handle(event, payload)
        #         results[name] = (success, error)
        #     except Exception as e:
        #         results[name] = (False, str(e))
        
        return results

    def get_registered_providers(self) -> list[str]:
        """Return list of registered provider names."""
        return list(self.providers.keys())


# Future provider interfaces (Phase 2)

class WebhookProvider:
    """Base class for webhook providers."""
    
    def handle(self, event: str, payload: dict) -> tuple[bool, Optional[str]]:
        """Handle a webhook event.
        
        Args:
            event: Event name
            payload: Event data
        
        Returns:
            Tuple of (success, error_message)
        """
        raise NotImplementedError("Subclasses must implement handle()")


# Example Phase 2 configuration:
# 
# webhooks:
#   - provider: webflow
#     site_id: xxx
#     secret: xxx
#   - provider: ghost
#     api_url: xxx
#     api_key: xxx
#   - provider: generic
#     url: https://hooks.slack.com/services/xxx
