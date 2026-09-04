"""Top inflows/outflows in the next 30 days, with source links for the UI (Phase 18)."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from apps.accounts.models import Organization
from apps.forecasting.services.analytics import _party_names
from apps.forecasting.services.inputs import assemble_inputs

WINDOW_DAYS = 30


def drivers(org: Organization, as_of: date, limit: int = 5) -> list[dict[str, Any]]:
    inputs = assemble_inputs(org, as_of)
    names = _party_names(org)
    end = as_of + timedelta(days=WINDOW_DAYS)
    rows: list[dict[str, Any]] = []
    for ar in inputs.ar:
        if as_of <= ar.due_date <= end:
            rows.append(
                {
                    "direction": "inflow",
                    "label": names.get(ar.party_key, ar.party_key),
                    "amount": str(ar.amount),
                    "date": ar.due_date.isoformat(),
                    "source": "invoice",
                    "party": ar.party_key,
                }
            )
    for ap in inputs.ap:
        if as_of <= ap.due_date <= end:
            rows.append(
                {
                    "direction": "outflow",
                    "label": names.get(ap.party_key or "", "Vendor bill"),
                    "amount": str(ap.amount),
                    "date": ap.due_date.isoformat(),
                    "source": "invoice",
                    "party": ap.party_key,
                }
            )
    for r in inputs.recurring:
        if as_of <= r.next_expected <= end:
            rows.append(
                {
                    "direction": "outflow",
                    "label": "Recurring expense",
                    "amount": str((r.amount * r.weight).quantize(Decimal("0.01"))),
                    "date": r.next_expected.isoformat(),
                    "source": "recurring",
                    "party": None,
                }
            )
    for f in inputs.fixed_lines:
        if as_of <= f.next_date <= end:
            rows.append(
                {
                    "direction": "inflow"
                    if str(f.direction).lower().endswith("inflow")
                    else "outflow",
                    "label": f.name,
                    "amount": str(f.amount),
                    "date": f.next_date.isoformat(),
                    "source": "fixed_line",
                    "party": None,
                }
            )
    for s in inputs.statutory:
        if as_of <= s.date <= end:
            rows.append(
                {
                    "direction": "outflow",
                    "label": "GSTR-3B payment",
                    "amount": str(s.amount),
                    "date": s.date.isoformat(),
                    "source": "statutory",
                    "party": None,
                }
            )
    inflows = sorted(
        (r for r in rows if r["direction"] == "inflow"),
        key=lambda r: Decimal(r["amount"]),
        reverse=True,
    )[:limit]
    outflows = sorted(
        (r for r in rows if r["direction"] == "outflow"),
        key=lambda r: Decimal(r["amount"]),
        reverse=True,
    )[:limit]
    return inflows + outflows
