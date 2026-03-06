import json

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Prometheus
    prometheus_url: str = "http://showback-prometheus:9090"

    # Fixed costs (monthly)
    droplet_cost: float = 24.0
    cloudflare_cost: float = 0.0
    domain_cost: float = 1.02  # $12.20/year = $1.02/mo

    # Cost allocation weights
    cpu_weight: float = 0.5
    memory_weight: float = 0.5

    # Host hardware (for What-If comparison)
    host_vcpus: int = 2
    host_memory_gb: int = 4
    host_disk_gb: int = 80

    # App boundaries — JSON string mapping app name to container names
    app_boundaries: str = '{"evm": ["evm-backend", "evm-frontend", "evm-db"], "equicalendar": ["equicalendar"], "planespotter": ["planespotter-api", "planespotter-frontend", "planespotter-sync", "planespotter-db", "planespotter-cache"], "meweb": ["meweb"], "greenscope": ["greenscope"], "infrastructure": ["prometheus", "grafana", "loki", "promtail", "node-exporter", "cadvisor", "ntfy", "showback"]}'

    # App display names — JSON string mapping internal name to friendly name
    app_display_names: str = '{"evm": "Equestrian Venue Manager", "equicalendar": "EquiCalendar", "planespotter": "Planespotter", "meweb": "dreamfold.dev", "greenscope": "GreenScope", "infrastructure": "Infrastructure"}'

    # Calculation interval
    calculation_interval_minutes: int = 15

    # Database
    database_url: str = "sqlite+aiosqlite:///data/showback.db"

    # Logging
    log_level: str = "INFO"

    model_config = {"env_prefix": "SHOWBACK_", "case_sensitive": False}

    def get_app_boundaries(self) -> dict[str, list[str]]:
        return json.loads(self.app_boundaries)

    def get_app_display_names(self) -> dict[str, str]:
        return json.loads(self.app_display_names)

    @property
    def total_monthly_cost(self) -> float:
        return self.droplet_cost + self.cloudflare_cost + self.domain_cost

    @property
    def app_count(self) -> int:
        return len(json.loads(self.app_boundaries))


settings = Settings()
