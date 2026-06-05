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


class OrgDataProvider:
    name = "base"

    def get_by_inn(self, inn: str) -> OrgData:
        raise NotImplementedError


class StubProvider(OrgDataProvider):
    """
    Offline/dev provider — returns deterministic fake data so the whole flow
    (lookup → save → display) works without any API key.
    """

    name = "stub"

    def get_by_inn(self, inn: str) -> OrgData:
        inn = (inn or "").strip()
        if not inn.isdigit() or len(inn) not in (10, 12):
            raise OrgLookupError("ИНН должен содержать 10 или 12 цифр.")
        return OrgData(
            inn=inn,
            name=f"ООО «Тест-{inn[-4:]}»",
            full_name=f'Общество с ограниченной ответственностью «Тест-{inn[-4:]}»',
            kpp=(inn[:4] + "01001") if len(inn) == 10 else "",
            ogrn="1" + inn.ljust(12, "0")[:12],
            address="г. Москва, ул. Примерная, д. 1",
            status="ACTIVE",
        )


class DaDataProvider(OrgDataProvider):
    """DaData suggestions API — findById/party by INN (free tier: 10k/day)."""

    name = "dadata"
    URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"

    def __init__(self):
        self.api_key = settings.DADATA_API_KEY
        if not self.api_key:
            raise OrgLookupError("Не задан DADATA_API_KEY.")

    def get_by_inn(self, inn: str) -> OrgData:
        inn = (inn or "").strip()
        if not inn.isdigit() or len(inn) not in (10, 12):
            raise OrgLookupError("ИНН должен содержать 10 или 12 цифр.")
        try:
            resp = requests.post(
                self.URL,
                json={"query": inn, "count": 1},
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

        if not suggestions:
            raise OrgLookupError(f"Организация с ИНН {inn} не найдена.")

        data = suggestions[0].get("data", {})
        name = data.get("name", {}) or {}
        address = data.get("address", {}) or {}
        state = data.get("state", {}) or {}
        return OrgData(
            inn=data.get("inn", inn),
            name=name.get("short_with_opf") or name.get("short") or suggestions[0].get("value", ""),
            full_name=name.get("full_with_opf") or name.get("full") or "",
            kpp=data.get("kpp") or "",
            ogrn=data.get("ogrn") or "",
            address=address.get("unrestricted_value") or address.get("value") or "",
            status=state.get("status") or "",
        )


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
