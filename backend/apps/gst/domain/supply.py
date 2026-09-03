"""Place of supply → supply type (PROJECT_SPECS §3.2).

Intra-state when supplier state == place-of-supply state; otherwise inter-state.
Export, SEZ and import are flagged explicitly by the caller and always attract IGST.
"""

from enum import StrEnum


class SupplyType(StrEnum):
    INTRA = "INTRA"
    INTER = "INTER"
    EXPORT = "EXPORT"
    SEZ = "SEZ"
    IMPORT = "IMPORT"

    @property
    def uses_igst(self) -> bool:
        """Every supply type except intra-state is taxed under a single IGST head."""
        return self is not SupplyType.INTRA


def determine_supply_type(
    supplier_state: str,
    pos_state: str,
    is_export: bool = False,
    is_sez: bool = False,
    is_import: bool = False,
) -> SupplyType:
    """Classify a supply. Flag precedence: import > export > SEZ > state comparison."""
    if is_import:
        return SupplyType.IMPORT
    if is_export:
        return SupplyType.EXPORT
    if is_sez:
        return SupplyType.SEZ
    if supplier_state == pos_state:
        return SupplyType.INTRA
    return SupplyType.INTER
