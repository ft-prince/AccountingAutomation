"""§3.2 place of supply → supply type. Intra when supplier state == POS state; else inter."""

import pytest

from apps.gst.domain.supply import SupplyType, determine_supply_type


def test_supply_type_members() -> None:
    assert {member.name for member in SupplyType} == {"INTRA", "INTER", "EXPORT", "SEZ", "IMPORT"}


def test_same_state_is_intra() -> None:
    assert determine_supply_type("27", "27") is SupplyType.INTRA


def test_different_state_is_inter() -> None:
    assert determine_supply_type("27", "29") is SupplyType.INTER


def test_export_flag_wins_over_state_comparison() -> None:
    assert determine_supply_type("27", "27", is_export=True) is SupplyType.EXPORT
    assert determine_supply_type("27", "99", is_export=True) is SupplyType.EXPORT


def test_sez_flag_wins_over_state_comparison() -> None:
    assert determine_supply_type("27", "27", is_sez=True) is SupplyType.SEZ


def test_import_flag_wins_over_everything() -> None:
    assert determine_supply_type("99", "27", is_import=True) is SupplyType.IMPORT
    assert determine_supply_type("99", "27", is_import=True, is_export=True) is SupplyType.IMPORT


def test_export_wins_over_sez_when_both_flagged() -> None:
    assert determine_supply_type("27", "27", is_export=True, is_sez=True) is SupplyType.EXPORT


@pytest.mark.parametrize(
    "supply_type",
    [SupplyType.INTER, SupplyType.EXPORT, SupplyType.SEZ, SupplyType.IMPORT],
)
def test_non_intra_types_use_igst(supply_type: SupplyType) -> None:
    assert supply_type.uses_igst is True


def test_intra_does_not_use_igst() -> None:
    assert SupplyType.INTRA.uses_igst is False
