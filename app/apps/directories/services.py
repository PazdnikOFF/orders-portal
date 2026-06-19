"""Organization lookup/upsert by INN (TЗ §12.2/§12.3, §14)."""
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.integrations.providers import OrgData, OrgLookupError, get_provider

from .models import Distributor, Organization

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


# --------------------------------------------------------------------------- #
# Distributors — separate admin-managed directory (один ИНН = один дистрибьютор)
# --------------------------------------------------------------------------- #
def lookup_distributor_data(inn: str) -> OrgData:
    """Resolve company data by INN via the provider (head office — first match)."""
    candidates = _provider_candidates(inn)
    if not candidates:
        raise OrgLookupError(f"Организация с ИНН {inn} не найдена.")
    return candidates[0]


def lookup_distributor_candidates(inn: str) -> list[OrgData]:
    """All organizations matching an INN (head office + branches by КПП)."""
    inn = (inn or "").strip()
    candidates = _provider_candidates(inn)
    if not candidates:
        raise OrgLookupError(f"Организация с ИНН {inn} не найдена.")
    return candidates


def create_distributor(data: OrgData) -> Distributor:
    """Create a Distributor from a chosen provider candidate (one INN = one)."""
    inn = (data.inn or "").strip()
    if Distributor.objects.filter(inn=inn).exists():
        raise OrgLookupError(f"Дистрибьютор с ИНН {inn} уже есть в справочнике.")
    provider_name = (settings.ORG_PROVIDER or "stub").lower()
    return Distributor.objects.create(
        inn=inn,
        name=data.name,
        full_name=data.full_name,
        kpp=data.kpp or "",
        ogrn=data.ogrn,
        address=data.address,
        status=data.status,
        source=provider_name,
        is_active=True,
        updated_at=timezone.now(),
    )


def create_distributor_from_inn(inn: str) -> Distributor:
    """Create by INN using the first candidate (no branch choice — used by API)."""
    if Distributor.objects.filter(inn=(inn or "").strip()).exists():
        raise OrgLookupError(f"Дистрибьютор с ИНН {inn} уже есть в справочнике.")
    return create_distributor(lookup_distributor_candidates(inn)[0])


def refresh_distributor_from_provider(distributor: Distributor) -> Distributor:
    """Re-pull a distributor's data from the provider by its INN."""
    data = lookup_distributor_data(distributor.inn)
    distributor.name = data.name or distributor.name
    distributor.full_name = data.full_name or distributor.full_name
    distributor.kpp = data.kpp or distributor.kpp
    distributor.ogrn = data.ogrn or distributor.ogrn
    distributor.address = data.address or distributor.address
    distributor.status = data.status or distributor.status
    distributor.updated_at = timezone.now()
    distributor.save()
    return distributor


def resolve_distributor(inn: str) -> Distributor:
    """
    Resolve an existing active distributor by INN (used by the REST API).
    Distributors are NOT auto-created here — only the admin adds them.
    """
    inn = (inn or "").strip()
    dist = Distributor.objects.filter(inn=inn).first()
    if dist is None:
        raise OrgLookupError(
            f"Дистрибьютор с ИНН {inn} не найден в справочнике. "
            f"Его должен сначала добавить администратор."
        )
    if not dist.is_active:
        raise OrgLookupError(f"Дистрибьютор с ИНН {inn} отключён.")
    return dist
