from .base import IntegrationAdapter, IntegrationProviderError
from .google import GmailAdapter
from .microsoft import OutlookAdapter
from .slack import SlackAdapter


SUPPORTED_PROVIDER_IDS = ("slack", "gmail", "outlook")
CATALOG_ONLY_PROVIDER_IDS = ("teams", "github", "webhooks")

_ADAPTERS: dict[str, IntegrationAdapter] = {
    adapter.provider_id: adapter
    for adapter in (SlackAdapter(), GmailAdapter(), OutlookAdapter())
}


def get_adapter(provider_id: str) -> IntegrationAdapter:
    adapter = _ADAPTERS.get(provider_id)
    if adapter is None:
        raise IntegrationProviderError("integration_not_supported", "This integration is not supported yet")
    return adapter
