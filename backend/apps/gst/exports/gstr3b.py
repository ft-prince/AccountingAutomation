"""GSTR-3B JSON builder.

Target shape: GSTN gstr1_3b v1.1.0 (offline utility manual dated 22-12-2025).
Mapping (PROJECT_SPECS §3.6, §3.7; confirmed invoices of the period only, §7.1):
  3.1(a) osup_det      outward intra/inter (not zero-rated)
  3.1(b) osup_zero     outward export + SEZ
  3.1(c) osup_nil_exmp zeros — v1 has no nil/exempt classification
  3.1(d) isup_rev      inward with is_reverse_charge (§3.6)
  3.1(e) osup_nongst   zeros — v1 has no non-GST classification
  3.2    unreg_details inter-state outward to parties without GSTIN, per pos
         comp_details  inter-state outward to composition parties, per pos
         uin_details   empty — UIN holders are not modelled
  4(A)(1) IMPG  eligible inward supply_type import (v1: every import is goods)
  4(A)(2) IMPS  zeros (see IMPG)
  4(A)(3) ISRC  eligible inward reverse charge that is not an import
  4(A)(4) ISD   zeros — no ISD credit model
  4(A)(5) OTH   eligible inward, not RCM, not import
  4(B)    itc_rev zeros — no reversal model; itc_net = Σ itc_avl − Σ itc_rev
  4(D)(1) RUL   inward with itc_eligible=False (§3.7 blocked credits)
  5       inward_sup zeros — no exempt/non-GST inward classification
"Eligible" means itc_eligible=True: a blocked invoice sits in 4(D) never in 4(A).
"""

from decimal import Decimal
from typing import Any

from django.db.models import F, QuerySet, Sum, Value
from django.db.models.functions import Coalesce, NullIf

from apps.gst.exports.common import (
    ZERO,
    confirmed_invoices,
    default_profile,
    money,
    period_month,
)
from apps.invoices.models import Direction, Invoice, SupplyKind

HEADS = {
    "txval": "taxable_value",
    "iamt": "igst",
    "camt": "cgst",
    "samt": "sgst",
    "csamt": "cess",
}
ITC_AVL_TYPES = ("IMPG", "IMPS", "ISRC", "ISD", "OTH")
ITC_REV_TYPES = ("RUL", "OTH")
ITC_INELG_TYPES = ("RUL", "OTH")
TAX_KEYS = ("iamt", "camt", "samt", "csamt")


def _sums(qs: QuerySet[Invoice], keys: tuple[str, ...]) -> dict[str, Decimal]:
    aggregates = qs.aggregate(**{k: Sum(HEADS[k]) for k in keys})
    return {k: money(aggregates[k]) for k in keys}


def _all_heads(qs: QuerySet[Invoice]) -> dict[str, Decimal]:
    return _sums(qs, ("txval", "iamt", "camt", "samt", "csamt"))


def _tax_heads(qs: QuerySet[Invoice]) -> dict[str, Decimal]:
    return _sums(qs, TAX_KEYS)


def _zero_heads(keys: tuple[str, ...]) -> dict[str, Decimal]:
    return dict.fromkeys(keys, ZERO)


def _by_pos(qs: QuerySet[Invoice]) -> list[dict[str, Any]]:
    rows = (
        qs.annotate(
            pos=Coalesce(NullIf(F("place_of_supply_state_code"), Value("")), F("party__state_code"))
        )
        .values("pos")
        .annotate(txval=Sum("taxable_value"), iamt=Sum("igst"))
        .order_by("pos")
    )
    return [
        {"pos": r["pos"] or "", "txval": money(r["txval"]), "iamt": money(r["iamt"])} for r in rows
    ]


def _add(a: dict[str, Decimal], b: dict[str, Decimal]) -> dict[str, Decimal]:
    return {k: a[k] + b[k] for k in TAX_KEYS}


def _sub(a: dict[str, Decimal], b: dict[str, Decimal]) -> dict[str, Decimal]:
    return {k: a[k] - b[k] for k in TAX_KEYS}


def build_gstr3b(org: Any, period: str) -> dict[str, Any]:
    month_label = period_month(period)
    profile = default_profile(org)
    base = confirmed_invoices(org, profile, month_label)
    outward = base.filter(direction=Direction.OUTWARD)
    inward = base.filter(direction=Direction.INWARD)
    eligible = inward.filter(itc_eligible=True)

    itc_avl = {
        "IMPG": _tax_heads(eligible.filter(supply_type=SupplyKind.IMPORT)),
        "IMPS": _zero_heads(TAX_KEYS),
        "ISRC": _tax_heads(
            eligible.filter(is_reverse_charge=True).exclude(supply_type=SupplyKind.IMPORT)
        ),
        "ISD": _zero_heads(TAX_KEYS),
        "OTH": _tax_heads(
            eligible.filter(is_reverse_charge=False).exclude(supply_type=SupplyKind.IMPORT)
        ),
    }
    itc_rev = {ty: _zero_heads(TAX_KEYS) for ty in ITC_REV_TYPES}
    itc_inelg = {
        "RUL": _tax_heads(inward.filter(itc_eligible=False)),
        "OTH": _zero_heads(TAX_KEYS),
    }
    total_avl = _zero_heads(TAX_KEYS)
    for heads in itc_avl.values():
        total_avl = _add(total_avl, heads)
    total_rev = _zero_heads(TAX_KEYS)
    for heads in itc_rev.values():
        total_rev = _add(total_rev, heads)

    unregistered = outward.filter(supply_type=SupplyKind.INTER).filter(
        party__gstin__isnull=True
    ) | outward.filter(supply_type=SupplyKind.INTER, party__gstin="")
    composition = outward.filter(supply_type=SupplyKind.INTER, party__is_composition=True)

    return {
        "gstin": profile.gstin,
        "ret_period": period,
        "sup_details": {
            "osup_det": _all_heads(
                outward.filter(supply_type__in=[SupplyKind.INTRA, SupplyKind.INTER])
            ),
            "osup_zero": _sums(
                outward.filter(supply_type__in=[SupplyKind.EXPORT, SupplyKind.SEZ]),
                ("txval", "iamt", "csamt"),
            ),
            "osup_nil_exmp": {"txval": ZERO},
            "isup_rev": _all_heads(inward.filter(is_reverse_charge=True)),
            "osup_nongst": {"txval": ZERO},
        },
        "inter_sup": {
            "unreg_details": _by_pos(unregistered),
            "comp_details": _by_pos(composition),
            "uin_details": [],
        },
        "itc_elg": {
            "itc_avl": [{"ty": ty, **itc_avl[ty]} for ty in ITC_AVL_TYPES],
            "itc_rev": [{"ty": ty, **itc_rev[ty]} for ty in ITC_REV_TYPES],
            "itc_net": _sub(total_avl, total_rev),
            "itc_inelg": [{"ty": ty, **itc_inelg[ty]} for ty in ITC_INELG_TYPES],
        },
        "inward_sup": {
            "isup_details": [
                {"ty": "GST", "inter": ZERO, "intra": ZERO},
                {"ty": "NONGST", "inter": ZERO, "intra": ZERO},
            ]
        },
    }
