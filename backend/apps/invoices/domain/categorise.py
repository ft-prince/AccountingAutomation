"""Line-level expense categorisation. PURE: no Django, no I/O.

Maps an invoice line (HSN/SAC + description) to one of the seeded expense
categories of PROJECT_SPECS §4. The category carries itc_eligible, so a wrong
category silently changes the §3.7 blocked-credit report — precedence is
therefore deterministic and rules-first: HSN/SAC code, then description
keyword, then the party default, then "Other".
"""

import re
from dataclasses import dataclass
from decimal import Decimal

SOFTWARE = "Software & SaaS"
MARKETING = "Marketing"
PROFESSIONAL = "Professional Services"
RENT = "Rent"
UTILITIES = "Utilities"
TRAVEL = "Travel"
MEALS = "Meals & Entertainment"
OFFICE = "Office Supplies"
HARDWARE = "Hardware & Equipment"
BANK_CHARGES = "Bank Charges"
SALARIES = "Salaries & Contractors"
INSURANCE = "Insurance"
FREIGHT = "Freight & Logistics"
REPAIRS = "Repairs & Maintenance"
STATUTORY = "Statutory Fees"
OTHER = "Other"

#: The seeded taxonomy (apps/parties/management/commands/seed_categories.py).
#: Nothing outside this set may ever be written as a category name — in
#: particular an LLM suggestion is discarded unless it is a member.
CATEGORY_NAMES: frozenset[str] = frozenset(
    {
        SOFTWARE,
        MARKETING,
        PROFESSIONAL,
        RENT,
        UTILITIES,
        TRAVEL,
        MEALS,
        OFFICE,
        HARDWARE,
        BANK_CHARGES,
        SALARIES,
        INSURANCE,
        FREIGHT,
        REPAIRS,
        STATUTORY,
        OTHER,
    }
)

HSN_CONFIDENCE = Decimal("0.90")
KEYWORD_CONFIDENCE = Decimal("0.70")
PARTY_DEFAULT_CONFIDENCE = Decimal("0.50")
FALLBACK_CONFIDENCE = Decimal("0.20")

_MIN_SINGULAR_LEN = 4
_WORD = re.compile(r"[a-z0-9]+")
_DIGITS = re.compile(r"\D")

# (code prefix, category). The longest matching prefix wins, so a specific
# six-digit SAC always beats its four-digit heading.
_HSN_RULES: tuple[tuple[str, str], ...] = (
    # --- Services, chapter 99 (SAC) -------------------------------------
    ("9963", MEALS),  # accommodation, food & beverage services; F&B ITC blocked §3.7
    ("9964", TRAVEL),  # passenger transport services
    ("9965", FREIGHT),  # goods transport services (996511 road freight upward)
    ("9967", FREIGHT),  # supporting services in transport (996713 clearing & forwarding)
    ("9968", FREIGHT),  # postal and courier services
    ("9969", UTILITIES),  # electricity, gas and water distribution services
    ("9971", BANK_CHARGES),  # financial services: bank commission, gateway fees
    ("99713", INSURANCE),  # insurance services sit inside heading 9971
    ("9972", RENT),  # real estate services (997212 rental of non-residential property)
    ("9973", RENT),  # leasing/rental of machinery & goods without operator
    ("997331", SOFTWARE),  # licensing services for the right to use computer software
    ("9982", PROFESSIONAL),  # legal and accounting services
    ("9983", PROFESSIONAL),  # other professional, technical and business services
    ("998313", SOFTWARE),  # IT consulting and support services
    ("998314", SOFTWARE),  # IT design and development services
    ("998315", SOFTWARE),  # hosting and IT infrastructure provisioning (cloud)
    ("99836", MARKETING),  # advertising services and provision of advertising space
    ("9984", UTILITIES),  # telecom, broadcasting and information supply (internet, phone)
    ("99851", SALARIES),  # employment/manpower supply services (contract staff)
    ("99855", TRAVEL),  # travel arrangement, tour operator and related services
    ("9987", REPAIRS),  # maintenance, repair and installation services
    ("9991", STATUTORY),  # public administration services: statutory and government fees
    # --- Goods (HSN) ----------------------------------------------------
    ("0901", MEALS),  # coffee
    ("0902", MEALS),  # tea
    ("1905", MEALS),  # bread, pastry, biscuits
    ("2106", MEALS),  # food preparations n.e.s.
    ("2202", MEALS),  # waters and non-alcoholic beverages
    ("2716", UTILITIES),  # electrical energy
    ("4817", OFFICE),  # envelopes, letter cards
    ("4820", OFFICE),  # registers, notebooks, office stationery
    ("4911", MARKETING),  # printed advertising material, brochures
    ("84", HARDWARE),  # machinery and mechanical appliances (8471 computers)
    ("85", HARDWARE),  # electrical machinery and electronics (8517 network gear)
    ("9608", OFFICE),  # pens and markers
    ("9609", OFFICE),  # pencils and crayons
)

# Ordered: the first phrase found in the description wins, so put the
# specific phrases before the generic word they contain.
_KEYWORD_RULES: tuple[tuple[str, str], ...] = (
    ("bank charge", BANK_CHARGES),
    ("processing fee", BANK_CHARGES),
    ("payment gateway", BANK_CHARGES),
    ("transaction charge", BANK_CHARGES),
    ("air ticket", TRAVEL),
    ("cab fare", TRAVEL),
    ("team lunch", MEALS),
    ("office rent", RENT),
    ("office supplie", OFFICE),  # normalised form of "office supplies"
    ("printer paper", OFFICE),
    ("annual maintenance", REPAIRS),
    ("software", SOFTWARE),
    ("saa", SOFTWARE),  # normalised form of "saas"
    ("subscription", SOFTWARE),
    ("licence", SOFTWARE),
    ("license", SOFTWARE),
    ("cloud", SOFTWARE),
    ("hosting", SOFTWARE),
    ("domain renewal", SOFTWARE),
    ("advertising", MARKETING),
    ("advertisement", MARKETING),
    ("marketing", MARKETING),
    ("campaign", MARKETING),
    ("branding", MARKETING),
    ("seo", MARKETING),
    ("consulting", PROFESSIONAL),
    ("consultancy", PROFESSIONAL),
    ("audit fee", PROFESSIONAL),
    ("legal", PROFESSIONAL),
    ("advocate", PROFESSIONAL),
    ("retainer", PROFESSIONAL),
    ("professional fee", PROFESSIONAL),
    ("rent", RENT),
    ("lease rental", RENT),
    ("electricity", UTILITIES),
    ("broadband", UTILITIES),
    ("internet", UTILITIES),
    ("telephone", UTILITIES),
    ("water charge", UTILITIES),
    ("travel", TRAVEL),
    ("flight", TRAVEL),
    ("hotel", TRAVEL),
    ("taxi", TRAVEL),
    ("lunch", MEALS),
    ("dinner", MEALS),
    ("meal", MEALS),
    ("catering", MEALS),
    ("restaurant", MEALS),
    ("refreshment", MEALS),
    ("snack", MEALS),
    ("stationery", OFFICE),
    ("cartridge", OFFICE),
    ("toner", OFFICE),
    ("laptop", HARDWARE),
    ("desktop", HARDWARE),
    ("monitor", HARDWARE),
    ("server", HARDWARE),
    ("router", HARDWARE),
    ("hardware", HARDWARE),
    ("salary", SALARIES),
    ("salarie", SALARIES),  # normalised form of "salaries"
    ("payroll", SALARIES),
    ("wage", SALARIES),
    ("contractor", SALARIES),
    ("freelance", SALARIES),
    ("manpower", SALARIES),
    ("insurance", INSURANCE),
    ("premium", INSURANCE),
    ("freight", FREIGHT),
    ("courier", FREIGHT),
    ("shipping", FREIGHT),
    ("logistic", FREIGHT),
    ("cartage", FREIGHT),
    ("repair", REPAIRS),
    ("maintenance", REPAIRS),
    ("amc", REPAIRS),
    ("installation", REPAIRS),
    ("challan", STATUTORY),
    ("statutory", STATUTORY),
    ("government fee", STATUTORY),
    ("registration fee", STATUTORY),
    ("filing fee", STATUTORY),
)

# Longest prefix first: "998315" must be tried before "9983".
_HSN_BY_LENGTH: tuple[tuple[str, str], ...] = tuple(
    sorted(_HSN_RULES, key=lambda rule: len(rule[0]), reverse=True)
)


@dataclass(frozen=True)
class CategorySuggestion:
    """A category name from CATEGORY_NAMES, how sure we are, and why."""

    name: str
    confidence: Decimal
    reason: str


def normalise(text: str) -> str:
    """Lowercase, drop punctuation, crudely singularise: 'Office Supplies' → 'office supplie'."""
    words = [
        word[:-1] if len(word) >= _MIN_SINGULAR_LEN and word.endswith("s") else word
        for word in _WORD.findall(text.lower())
    ]
    return " ".join(words)


def match_hsn(hsn_sac: str) -> tuple[str, str] | None:
    """Longest HSN/SAC prefix wins. Returns (category, reason) or None."""
    code = _DIGITS.sub("", hsn_sac)
    if not code:
        return None
    for prefix, category in _HSN_BY_LENGTH:
        if code.startswith(prefix):
            return category, f"HSN/SAC {code} matches {prefix}"
    return None


def match_keyword(description: str) -> tuple[str, str] | None:
    """First keyword phrase present as whole words wins. Returns (category, reason) or None."""
    haystack = f" {normalise(description)} "
    for phrase, category in _KEYWORD_RULES:
        if f" {phrase} " in haystack:
            return category, f"description mentions '{phrase}'"
    return None


def suggest_category(
    hsn_sac: str, description: str, party_default: str | None
) -> CategorySuggestion:
    """Rules-only suggestion. Precedence: HSN/SAC → keyword → party default → Other."""
    by_code = match_hsn(hsn_sac)
    if by_code is not None:
        return CategorySuggestion(by_code[0], HSN_CONFIDENCE, by_code[1])
    by_word = match_keyword(description)
    if by_word is not None:
        return CategorySuggestion(by_word[0], KEYWORD_CONFIDENCE, by_word[1])
    if party_default:
        # An org may have its own categories beyond the seed, so the party
        # default is passed through by name rather than checked against the seed.
        return CategorySuggestion(
            party_default, PARTY_DEFAULT_CONFIDENCE, "no line signal; party default category"
        )
    return CategorySuggestion(OTHER, FALLBACK_CONFIDENCE, "no rule matched")
