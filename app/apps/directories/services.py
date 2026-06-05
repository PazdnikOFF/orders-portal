"""Organization lookup/upsert by INN (TЗ §12.2/§12.3, §14)."""
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.integrations.providers import OrgData, OrgLookupError, get_provider

from .models import Organization

CACHE_PREFIX = "org_suggest:"


def _provider_candidates(inn: str) -> list[OrgData]:
    """Fetch candidates via the provider, with a short Redis cache."""
    inn = (inn or "").strip()
    cache_key = f"{CACHE_PREFIX}{inn}"
    cached = cache.get(cache_key)
    if cached is not None:
        return [OrgData(**d) for d in cached]

    data = get_provider().get_candidates(inn)
    cache.set(cache_key, [d.as_dict() for d in data], settings.ORG_LOOKUP_CACHE_TTL)
    return data


def _upsert_one(data: OrgData) -> Organization:
    """Create/update an Organization keyed by (inn, kpp)."""
    provider_name = (settings.ORG_PROVIDER or "stub").lower()
    org, _created = Organization.objects.update_or_create(
        inn=data.inn, kpp=data.kpp or "",
        defaults={
            "name": data.name,
            "full_name": data.full_name,
            "ogrn": data.ogrn,
            "address": data.address,
            "status": data.status,
            "source": provider_name,
            "updated_at": timezone.now(),
        },
    )
    return org


def suggest_orgs(inn: str) -> list[Organization]:
    """
    Look up an INN and return all matching organizations (head office +
    branches), upserted locally so each has a stable id for the combobox.
    """
    return [_upsert_one(d) for d in _provider_candidates(inn)]


def upsert_organization(inn: str) -> Organization:
    """Resolve a single organization by INN (used by the REST API)."""
    candidates = _provider_candidates(inn)
    if not candidates:
        raise OrgLookupError(f"Организация с ИНН {inn} не найдена.")
    return _upsert_one(candidates[0])
