"""Idempotent system category seed. PROJECT_SPECS §4 seed list, §3.7 blocked credits."""

from django.core.management.base import BaseCommand

from apps.parties.models import ExpenseCategory

# (name, itc_eligible, section_17_5_ref, tally_ledger_name, is_recurring_hint)
SEED: list[tuple[str, bool, str, str, bool]] = [
    ("Software & SaaS", True, "", "Software Subscriptions", True),
    ("Marketing", True, "", "Advertisement & Marketing", False),
    ("Professional Services", True, "", "Professional Fees", False),
    ("Rent", True, "", "Rent", True),
    ("Utilities", True, "", "Electricity & Utilities", True),
    ("Travel", True, "", "Travelling Expenses", False),
    ("Meals & Entertainment", False, "17(5)(b)(i)", "Staff Welfare", False),
    ("Office Supplies", True, "", "Office Expenses", False),
    ("Hardware & Equipment", True, "", "Computer & Equipment", False),
    ("Bank Charges", True, "", "Bank Charges", True),
    ("Salaries & Contractors", True, "", "Salaries & Wages", True),
    ("Insurance", True, "", "Insurance", True),
    ("Freight & Logistics", True, "", "Freight & Forwarding", False),
    ("Repairs & Maintenance", True, "", "Repairs & Maintenance", False),
    ("Statutory Fees", True, "", "Rates & Taxes", False),
    ("Other", True, "", "Miscellaneous Expenses", False),
]


class Command(BaseCommand):
    help = "Seed system expense categories (idempotent)."

    def handle(self, *args: object, **options: object) -> None:
        created = 0
        for name, itc, ref, ledger, recurring in SEED:
            _, was_created = ExpenseCategory.objects.get_or_create(
                org=None,
                name=name,
                defaults={
                    "itc_eligible": itc,
                    "section_17_5_ref": ref,
                    "tally_ledger_name": ledger,
                    "is_recurring_hint": recurring,
                },
            )
            created += int(was_created)
        self.stdout.write(f"seed_categories: {created} created, {len(SEED) - created} existing")
