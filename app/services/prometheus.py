import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class PrometheusClient:
    """Async client for querying the Prometheus HTTP API."""

    def __init__(self) -> None:
        self.base_url = settings.prometheus_url

    async def get_container_cpu_seconds(
        self,
        container_names: list[str],
        period_seconds: int,
    ) -> dict[str, float]:
        """Get CPU seconds consumed per container over the measurement period."""
        names_regex = "|".join(container_names)
        query = f'sum by (name) (increase(container_cpu_usage_seconds_total{{name=~"{names_regex}"}}[{period_seconds}s]))'

        result = await self._query(query)
        cpu_by_container: dict[str, float] = {}

        for item in result:
            name = item["metric"].get("name", "")
            value = float(item["value"][1])
            cpu_by_container[name] = value

        return cpu_by_container

    async def get_container_memory_avg(
        self,
        container_names: list[str],
        period_seconds: int,
    ) -> dict[str, float]:
        """Get average memory usage in bytes per container over the measurement period."""
        names_regex = "|".join(container_names)
        query = f'avg_over_time(container_memory_usage_bytes{{name=~"{names_regex}"}}[{period_seconds}s])'

        result = await self._query(query)
        mem_by_container: dict[str, float] = {}

        for item in result:
            name = item["metric"].get("name", "")
            value = float(item["value"][1])
            mem_by_container[name] = value

        return mem_by_container

    async def get_container_network_bytes(
        self,
        container_names: list[str],
        period_seconds: int,
    ) -> dict[str, float]:
        """Get total network bytes (tx + rx) per container over the measurement period."""
        names_regex = "|".join(container_names)
        tx_query = f'sum by (name) (increase(container_network_transmit_bytes_total{{name=~"{names_regex}"}}[{period_seconds}s]))'
        rx_query = f'sum by (name) (increase(container_network_receive_bytes_total{{name=~"{names_regex}"}}[{period_seconds}s]))'

        tx_result = await self._query(tx_query)
        rx_result = await self._query(rx_query)

        net_by_container: dict[str, float] = {}

        for item in tx_result:
            name = item["metric"].get("name", "")
            value = float(item["value"][1])
            net_by_container[name] = net_by_container.get(name, 0) + value

        for item in rx_result:
            name = item["metric"].get("name", "")
            value = float(item["value"][1])
            net_by_container[name] = net_by_container.get(name, 0) + value

        return net_by_container

    async def _query(self, promql: str) -> list[dict]:
        """Execute a PromQL instant query."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/query",
                    params={"query": promql},
                )
                response.raise_for_status()
                data = response.json()

                if data.get("status") != "success":
                    logger.warning("Prometheus query failed: %s", data.get("error", "unknown"))
                    return []

                return data.get("data", {}).get("result", [])

        except Exception as e:
            logger.warning("Prometheus query error (%s): %s", promql[:80], e)
            return []
