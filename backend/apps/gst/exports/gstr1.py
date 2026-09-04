"""GSTR-1 JSON builder.

Target shape: GSTN "Save GSTR-1" API payload, schema label file/save v4.1 (the format the
GSTN offline tool imports). Dates DD-MM-YYYY, rates as integers when whole, amounts as
JSON numbers with 2 dp — see common.to_json for the single Decimal→number boundary.
Bundled structural schema: schemas/gstr1_v4_1.json.

Sections emitted (all from CONFIRMED outward invoices of the period, §7.1):
  b2b   party has a GSTIN                              inv_typ R / SEZWP / SEZWOP
  b2cl  no GSTIN, inter-state, total > B2CL_THRESHOLD  grouped by pos
  b2cs  every other B2C invoice, aggregated per (sply_ty, pos, rate), typ "OE"
  exp   supply_type export; WPAY when IGST was charged, else WOPAY;
        shipping-bill fields are blank strings (not captured by extraction, v1)
  cdnr  always empty — v1 has no credit/debit-note model
  hsn   aggregated per (hsn_sac, rate); uqc = uom upper-cased, default "OTH";
        header-only invoices (no lines) carry no HSN and are not summarised
  nil   zeros — v1 does not classify nil-rated / exempt / non-GST supplies
  doc_issue  one series: count of confirmed outward invoices; from/to only when a
        numeric suffix is parsable on the invoice numbers
"""

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db.models import Sum

from apps.accounts.models import GSTINProfile
from apps.gst.domain.periods import fy_bounds, fy_for_date
from apps.gst.exports.common import (
    HUNDRED,
    TWO_DP,
    ZERO,
    confirmed_invoices,
    default_profile,
    gstn_date,
    money,
    period_month,
    period_start,
    rate_number,
)
from apps.invoices.models import Direction, Invoice, InvoiceStatus, SupplyKind

# B2CL: inter-state supplies to unregistered persons reported invoice-wise above this
# invoice value. ₹2,50,000 originally; lowered to ₹1,00,000 by Notification 12/2024-CT
# effective 01-08-2024. Data, not logic — verify at go-live (PROJECT_SPECS §3.3 rule).
B2CL_THRESHOLD = Decimal("100000.00")
DEFAULT_UQC = "OTH"
HSN_DESC_MAX = 30
NIL_SUPPLY_TYPES = ("INTRB2B", "INTRB2C", "INTRAB2B", "INTRAB2C")
_NUMERIC_SUFFIX = re.compile(r"(\d+)$")


@dataclass(frozen=True)
class Item:
    rate: Decimal
    txval: Decimal
    iamt: Decimal
    camt: Decimal
    samt: Decimal
    csamt: Decimal
    hsn: str
    desc: str
    uqc: str
    qty: Decimal


def _derived_rate(inv: Invoice) -> Decimal:
    if inv.taxable_value <= ZERO:
        return ZERO
    tax = inv.cgst + inv.sgst + inv.igst
    return (tax * HUNDRED / inv.taxable_value).quantize(TWO_DP, rounding=ROUND_HALF_UP)


def invoice_items(inv: Invoice) -> list[Item]:
    """Line items; a header-only invoice becomes one item with the rate derived from tax."""
    lines = list(inv.lines.all())
    if not lines:
        return [
            Item(
                _derived_rate(inv),
                money(inv.taxable_value),
                money(inv.igst),
                money(inv.cgst),
                money(inv.sgst),
                money(inv.cess),
                "",
                "",
                DEFAULT_UQC,
                Decimal("1"),
            )
        ]
    return [
        Item(
            line.rate,
            money(line.taxable_value),
            money(line.igst),
            money(line.cgst),
            money(line.sgst),
            money(line.cess),
            line.hsn_sac.strip(),
            line.description[:HSN_DESC_MAX],
            line.uom.strip().upper() or DEFAULT_UQC,
            line.quantity,
        )
        for line in lines
    ]


def _pos(inv: Invoice, profile: GSTINProfile) -> str:
    return inv.place_of_supply_state_code or inv.party.state_code or profile.state_code


def _rchrg(inv: Invoice) -> str:
    return "Y" if inv.is_reverse_charge else "N"


def _inv_typ(inv: Invoice) -> str:
    if inv.supply_type == SupplyKind.SEZ:
        return "SEZWP" if inv.igst > ZERO else "SEZWOP"
    return "R"


def _b2b_items(items: list[Item]) -> list[dict[str, Any]]:
    return [
        {
            "num": n,
            "itm_det": {
                "rt": rate_number(it.rate),
                "txval": it.txval,
                "iamt": it.iamt,
                "camt": it.camt,
                "samt": it.samt,
                "csamt": it.csamt,
            },
        }
        for n, it in enumerate(items, start=1)
    ]


def _b2cl_items(items: list[Item]) -> list[dict[str, Any]]:
    return [
        {
            "num": n,
            "itm_det": {
                "rt": rate_number(it.rate),
                "txval": it.txval,
                "iamt": it.iamt,
                "csamt": it.csamt,
            },
        }
        for n, it in enumerate(items, start=1)
    ]


def _exp_items(items: list[Item]) -> list[dict[str, Any]]:
    return [
        {"txval": it.txval, "rt": rate_number(it.rate), "iamt": it.iamt, "csamt": it.csamt}
        for it in items
    ]


def _section(inv: Invoice) -> str:
    if inv.supply_type == SupplyKind.EXPORT:
        return "exp"
    if inv.party.gstin:
        return "b2b"
    if inv.supply_type == SupplyKind.INTER and inv.total > B2CL_THRESHOLD:
        return "b2cl"
    return "b2cs"


def _turnover(org: Any, profile: GSTINProfile, start: Any, end: Any) -> Decimal:
    total = (
        Invoice.objects.for_org(org)
        .filter(
            status=InvoiceStatus.CONFIRMED,
            direction=Direction.OUTWARD,
            invoice_date__range=(start, end),
        )
        .aggregate(s=Sum("total"))["s"]
    )
    return money(total)


def _doc_issue(invoices: list[Invoice]) -> dict[str, Any]:
    numbered = [
        (int(m.group(1)), inv.invoice_number)
        for inv in invoices
        if (m := _NUMERIC_SUFFIX.search(inv.invoice_number))
    ]
    doc: dict[str, Any] = {
        "num": 1,
        "totnum": len(invoices),
        "cancel": 0,
        "net_issue": len(invoices),
    }
    if numbered:
        doc = {**doc, "from": min(numbered)[1], "to": max(numbered)[1]}
    return {"doc_det": [{"doc_num": 1, "docs": [doc]}]}


def _hsn_summary(all_items: list[Item]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, Decimal], dict[str, Any]] = {}
    for it in all_items:
        if not it.hsn:
            continue
        key = (it.hsn, it.rate)
        row = buckets.get(key)
        if row is None:
            buckets[key] = {
                "hsn_sc": it.hsn,
                "desc": it.desc,
                "uqc": it.uqc,
                "qty": it.qty,
                "txval": it.txval,
                "iamt": it.iamt,
                "camt": it.camt,
                "samt": it.samt,
                "csamt": it.csamt,
                "rt": rate_number(it.rate),
            }
            continue
        buckets[key] = {
            **row,
            "qty": row["qty"] + it.qty,
            "txval": row["txval"] + it.txval,
            "iamt": row["iamt"] + it.iamt,
            "camt": row["camt"] + it.camt,
            "samt": row["samt"] + it.samt,
            "csamt": row["csamt"] + it.csamt,
        }
    ordered = sorted(buckets.items(), key=lambda kv: (kv[0][0], kv[0][1]))
    return [{"num": n, **row} for n, (_key, row) in enumerate(ordered, start=1)]


def build_gstr1(org: Any, period: str) -> dict[str, Any]:
    month_label = period_month(period)
    profile = default_profile(org)
    invoices = list(
        confirmed_invoices(org, profile, month_label).filter(direction=Direction.OUTWARD)
    )

    b2b: dict[str, list[dict[str, Any]]] = defaultdict(list)
    b2cl: dict[str, list[dict[str, Any]]] = defaultdict(list)
    b2cs: dict[tuple[str, str, Decimal], dict[str, Any]] = {}
    exp: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_items: list[Item] = []

    for inv in invoices:
        items = invoice_items(inv)
        all_items.extend(items)
        section = _section(inv)
        common = {
            "inum": inv.invoice_number,
            "idt": gstn_date(inv.invoice_date),
            "val": money(inv.total),
        }
        if section == "b2b":
            b2b[str(inv.party.gstin)].append(
                {
                    **common,
                    "pos": _pos(inv, profile),
                    "rchrg": _rchrg(inv),
                    "inv_typ": _inv_typ(inv),
                    "itms": _b2b_items(items),
                }
            )
        elif section == "b2cl":
            b2cl[_pos(inv, profile)].append({**common, "itms": _b2cl_items(items)})
        elif section == "exp":
            exp_typ = "WPAY" if inv.igst > ZERO else "WOPAY"
            exp[exp_typ].append(
                {**common, "sbpcode": "", "sbnum": "", "sbdt": "", "itms": _exp_items(items)}
            )
        else:
            sply_ty = "INTER" if inv.supply_type == SupplyKind.INTER else "INTRA"
            pos = _pos(inv, profile)
            for it in items:
                key = (sply_ty, pos, it.rate)
                row = b2cs.get(key) or {
                    "sply_ty": sply_ty,
                    "pos": pos,
                    "typ": "OE",
                    "rt": rate_number(it.rate),
                    "txval": ZERO,
                    "iamt": ZERO,
                    "camt": ZERO,
                    "samt": ZERO,
                    "csamt": ZERO,
                }
                b2cs[key] = {
                    **row,
                    "txval": row["txval"] + it.txval,
                    "iamt": row["iamt"] + it.iamt,
                    "camt": row["camt"] + it.camt,
                    "samt": row["samt"] + it.samt,
                    "csamt": row["csamt"] + it.csamt,
                }

    start = period_start(period)
    fy_start, _ = fy_bounds(fy_for_date(start))
    prev_start, prev_end = fy_bounds(fy_for_date(fy_start - timedelta(days=1)))
    period_end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

    return {
        "gstin": profile.gstin,
        "fp": period,
        "gt": _turnover(org, profile, prev_start, prev_end),
        "cur_gt": _turnover(org, profile, fy_start, period_end),
        "b2b": [{"ctin": ctin, "inv": rows} for ctin, rows in sorted(b2b.items())],
        "b2cl": [{"pos": pos, "inv": rows} for pos, rows in sorted(b2cl.items())],
        "b2cs": [row for _key, row in sorted(b2cs.items())],
        "cdnr": [],  # no credit/debit-note model in v1
        "exp": [{"exp_typ": typ, "inv": rows} for typ, rows in sorted(exp.items())],
        "hsn": {"data": _hsn_summary(all_items)},
        "nil": {
            "inv": [
                {"sply_ty": s, "nil_amt": ZERO, "expt_amt": ZERO, "ngsup_amt": ZERO}
                for s in NIL_SUPPLY_TYPES
            ]
        },
        "doc_issue": _doc_issue(invoices),
    }
