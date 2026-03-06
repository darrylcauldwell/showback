from prometheus_client import Gauge

COST_PER_APP_GAUGE = Gauge(
    "showback_cost_usd",
    "Allocated cost in USD per calculation period",
    ["app"],
)

CPU_SHARE_GAUGE = Gauge(
    "showback_cpu_share",
    "CPU usage share (0-1)",
    ["app"],
)

MEMORY_SHARE_GAUGE = Gauge(
    "showback_memory_share",
    "Memory usage share (0-1)",
    ["app"],
)

TOTAL_MONTHLY_COST_GAUGE = Gauge(
    "showback_total_monthly_cost_usd",
    "Total monthly infrastructure cost in USD",
)
