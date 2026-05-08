from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ServiceInfo:
    service_display_name: str
    numero_plano: int | None = None


@dataclass(slots=True)
class ClientInfo:
    id_cliente: int
    service: ServiceInfo
