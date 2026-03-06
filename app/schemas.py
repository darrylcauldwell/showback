from datetime import datetime

from pydantic import BaseModel


class CostComponent(BaseModel):
    app_name: str
    timestamp: datetime
    cpu_seconds: float
    memory_bytes_avg: float
    network_bytes: float
    cpu_share: float
    memory_share: float
    network_share: float
    droplet_cost: float
    cloudflare_cost: float
    domain_cost: float
    total_cost: float
    calculation_period_seconds: int

    model_config = {"from_attributes": True}


class CostCurrentResponse(BaseModel):
    scores: list[CostComponent]
    total_monthly_cost: float
    droplet_monthly: float
    cloudflare_monthly: float
    domain_monthly: float
    calculated_at: datetime


class CostHistoryResponse(BaseModel):
    app_name: str
    scores: list[CostComponent]
    hours: int


class AggregatedAppCost(BaseModel):
    app_name: str
    cpu_seconds: float
    memory_bytes_avg: float
    network_bytes: float
    cpu_share: float
    memory_share: float
    network_share: float
    droplet_cost: float
    cloudflare_cost: float
    domain_cost: float
    total_cost: float
    snapshot_count: int


class DropletSummary(BaseModel):
    total_cost: float
    droplet_cost: float
    cloudflare_cost: float
    domain_cost: float
    container_count: int


class AggregatedCostResponse(BaseModel):
    window_minutes: int
    scores: list[AggregatedAppCost]
    droplet: DropletSummary | None = None
    display_names: dict[str, str]
    boundaries: dict[str, list[str]]
