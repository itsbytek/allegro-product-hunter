from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ExternalCheck:
    provider: str
    status: str = "NOT_CONFIGURED"
    price: float | None = None
    url: str | None = None
    risk: str = "UNKNOWN"


class ExternalCompetitionProvider:
    name: str

    async def search(self, _name: str, _ean: str | None) -> ExternalCheck:
        raise NotImplementedError


class ManualExternalProvider(ExternalCompetitionProvider):
    def __init__(self, name: str):
        self.name = name

    async def search(self, _name: str, _ean: str | None) -> ExternalCheck:
        # Temu/AliExpress do not expose an official integration configured by this app.
        return ExternalCheck(provider=self.name)
