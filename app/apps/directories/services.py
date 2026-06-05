"""Organization upsert-by-INN service (TЗ §12.2/§12.3, §14)."""
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone

from apps.integrations.providers import OrgData, OrgLookupError, get_provider

from .models import Organization

CACHE_PREFIX = "org_lookup:"


def lookup_org_data(inn: str) -> OrgData:
    """
    Fetch organization data by INN via the configured provider, with a short
    Redis cache to avoid hammering the external API on repeated keystrokes.
    """
    inn = (inn or "").strip()
    cache_key = f"{CACHE_PREFIX}{inn}"
    cached = cache.get(cache_key)
    if cached:
        return OrgData(**cached)

    provider = get_provider()
    data = provider.get_by_inn(inn)
    cache.set(cache_key, data.as_dict(), settings.ORG_LOOKUP_CACHE_TTL)
    return data


def upsert_organization(inn: str) -> Organization:
    """
    Look up the org by INN and create/update the local record (amendment §7:
    «Если организация с таким ИНН уже есть в базе, данные обновляются»).
    """
    data = lookup_org_data(inn)
    provider_name = (settings.ORG_PROVIDER or "stub").lower()
    org, _created = Organization.objects.update_or_create(
        inn=data.inn,
        defaults={
            "name": data.name,
            "full_name": data.full_name,
            "kpp": data.kpp,
            "ogrn": data.ogrn,
            "address": data.address,
            "status": data.status,
            "source": provider_name,
            "updated_at": timezone.now(),
        },
    )
    return org
