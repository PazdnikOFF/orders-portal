"""
Organization data provider abstraction (TЗ §14).

The portal looks up companies by INN. Rusprofile has no stable public API, so
the default backend is DaData (free tier, findById/party). Everything is hidden
behind `OrgDataProvider`, so swapping to a Rusprofile/Bitrix backend later means
adding one class and flipping ORG_PROVIDER — no caller changes.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass

import requests
from django.conf import settings

logger = logging.getLogger("apps.integrations")


@dataclass
class OrgData:
    inn: str
    name: str = ""           # короткое наименование с ОПФ
    full_name: str = ""      # полное наименование
    kpp: str = ""
    ogrn: str = ""
    address: str = ""
    status: str = ""         # ACTIVE / LIQUIDATED / ...

    def as_dict(self) -> dict:
        return asdict(self)


class OrgLookupError(Exception):
    """Raised when the provider cannot return data for the given INN."""


def _validate_inn(inn: str) -> str:
    inn = (inn or "").strip()
    if not inn.isdigit() or len(inn) not in (10, 12):
        raise OrgLookupError("ИНН должен содержать 10 или 12 цифр.")
    return inn


class OrgDataProvider:
    name = "base"

    def get_candidates(self, inn: str, count: int = 7) -> list[OrgData]:
        """Return all organizations matching the INN (head office + branches)."""
        raise NotImplementedError

    def get_by_inn(self, inn: str) -> OrgData:
        candidates = self.get_candidates(inn, count=1)
        if not candidates:
            raise OrgLookupError(f"Организация с ИНН {inn} не найдена.")
        return candidates[0]


class StubProvider(OrgDataProvider):
    """
    Offline/dev provider — returns deterministic fake data (with a couple of КПП
    variants for 10-digit INNs) so the full flow works without any API key.
    """

    name = "stub"

    def get_candidates(self, inn: str, count: int = 7) -> list[OrgData]:
        inn = _validate_inn(inn)
        suffix = inn[-4:]
        head = OrgData(
            inn=inn,
            name=f"ООО «Тест-{suffix}»",
            full_name=f'Общество с ограниченной ответственностью «Тест-{suffix}»',
            kpp=(inn[:4] + "01001") if len(inn) == 10 else "",
            ogrn="1" + inn.ljust(12, "0")[:12],
            address="г. Москва, ул. Примерная, д. 1",
            status="ACTIVE",
        )
        result = [head]
        if len(inn) == 10 and count > 1:  # simulate a branch with another КПП
            result.append(OrgData(
                inn=inn, name=head.name, full_name=head.full_name,
                kpp=inn[:4] + "02001", ogrn=head.ogrn,
                address="г. Санкт-Петербург, Невский пр., д. 2 (филиал)",
                status="ACTIVE",
            ))
        return result[:count]


class DaDataProvider(OrgDataProvider):
    """DaData suggestions API — findById/party by INN (free tier: 10k/day)."""

    name = "dadata"
    URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"

    def __init__(self):
        self.api_key = settings.DADATA_API_KEY
        if not self.api_key:
            raise OrgLookupError("Не задан DADATA_API_KEY.")

    @staticmethod
    def _parse(suggestion: dict, fallback_inn: str) -> OrgData:
        data = suggestion.get("data", {}) or {}
        name = data.get("name", {}) or {}
        address = data.get("address", {}) or {}
        state = data.get("state", {}) or {}
        return OrgData(
            inn=data.get("inn", fallback_inn),
            name=name.get("short_with_opf") or name.get("short") or suggestion.get("value", ""),
            full_name=name.get("full_with_opf") or name.get("full") or "",
            kpp=data.get("kpp") or "",
            ogrn=data.get("ogrn") or "",
            address=address.get("unrestricted_value") or address.get("value") or "",
            status=state.get("status") or "",
        )

    def get_candidates(self, inn: str, count: int = 7) -> list[OrgData]:
        inn = _validate_inn(inn)
        try:
            resp = requests.post(
                self.URL,
                json={"query": inn, "count": max(1, min(count, 20))},
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Token {self.api_key}",
                },
                timeout=10,
            )
            resp.raise_for_status()
            suggestions = resp.json().get("suggestions") or []
        except requests.RequestException as exc:
            logger.warning("DaData lookup failed for %s: %s", inn, exc)
            raise OrgLookupError("Сервис данных организаций недоступен.") from exc

        return [self._parse(s, inn) for s in suggestions]


_PROVIDERS = {
    "stub": StubProvider,
    "dadata": DaDataProvider,
}


def get_provider() -> OrgDataProvider:
    """Instantiate the configured provider (ORG_PROVIDER)."""
    key = (settings.ORG_PROVIDER or "stub").lower()
    provider_cls = _PROVIDERS.get(key)
    if provider_cls is None:
        raise OrgLookupError(f"Неизвестный провайдер организаций: {key}")
    return provider_cls()
