"""§8.8: Claude-generated five-bullet summary from aggregates only, guarded by the pure checker."""

import logging
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from django.conf import settings

from apps.forecasting.domain.narrative import check_bullets, numbers_in
from apps.forecasting.models import ForecastPoint, ForecastRun

log = logging.getLogger(__name__)
PROMPT_VERSION = "forecast_narrative_v1"
PROMPT_PATH = Path(settings.BASE_DIR) / "prompts" / f"{PROMPT_VERSION}.txt"
TOOL: dict[str, Any] = {
    "name": "write_summary",
    "description": "Five plain-English bullets.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "bullets": {"type": "array", "items": {"type": "string"}, "minItems": 5, "maxItems": 5}
        },
        "required": ["bullets"],
        "additionalProperties": False,
    },
}


def _money(v: Decimal | None) -> str:
    return "n/a" if v is None else f"{v:,.2f}"


def aggregates_for(
    run: ForecastRun, *, drivers: list[dict[str, Any]], high_risk: list[str]
) -> dict[str, Any]:
    """ONLY aggregates leave the system: no invoice-level data."""
    points = list(ForecastPoint.objects.filter(run=run).order_by("date"))
    day30 = points[min(29, len(points) - 1)] if points else None
    return {
        "as_of": run.as_of.isoformat(),
        "opening_cash": _money(points[0].deterministic if points else None),
        "day30_p10": _money(day30.p10 if day30 else None),
        "day30_p50": _money(day30.p50 if day30 else None),
        "day30_p90": _money(day30.p90 if day30 else None),
        "runway_date": run.runway_date.isoformat() if run.runway_date else "beyond horizon",
        "backtest_coverage_pct": _money(run.backtest_coverage * 100)
        if run.backtest_coverage is not None
        else "n/a",
        "top_inflows": [
            {"label": d["label"], "amount": _money(Decimal(d["amount"]))}
            for d in drivers
            if d["direction"] == "inflow"
        ][:3],
        "top_outflows": [
            {"label": d["label"], "amount": _money(Decimal(d["amount"]))}
            for d in drivers
            if d["direction"] == "outflow"
        ][:3],
        "high_risk_customers": high_risk[:5],
    }


def generate_narrative(
    run: ForecastRun, aggregates: dict[str, Any], *, client: Any | None = None
) -> str | None:
    """Returns the accepted bullets joined by newlines, or None (with the reason logged)."""
    import json

    import anthropic

    if client is None:
        if not settings.ANTHROPIC_API_KEY:
            return None
        client = cast(Any, anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=2))
    resp = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=1024,
        system=PROMPT_PATH.read_text(),
        tools=[TOOL],
        tool_choice={"type": "tool", "name": "write_summary"},
        messages=[{"role": "user", "content": json.dumps(aggregates, ensure_ascii=False)}],
    )
    tool_input = next((b.input for b in resp.content if b.type == "tool_use"), None)
    bullets = list(tool_input.get("bullets", [])) if isinstance(tool_input, dict) else []
    allowed = numbers_in(json.dumps(aggregates, ensure_ascii=False))
    result = check_bullets(bullets, allowed)
    if not result.ok:
        log.warning("narrative rejected", extra={"run": str(run.pk), "rejected": result.rejected})
        run.narrative = None
        run.save(update_fields=["narrative", "updated_at"])
        return None
    run.narrative = "\n".join(result.accepted)
    run.save(update_fields=["narrative", "updated_at"])
    return run.narrative
