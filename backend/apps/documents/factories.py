import hashlib

import factory

from apps.accounts.factories import OrganizationFactory
from apps.documents.models import Document


class DocumentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Document

    org = factory.SubFactory(OrganizationFactory)
    file = factory.Sequence(lambda n: f"org/x/documents/{n}")
    sha256 = factory.Sequence(lambda n: hashlib.sha256(str(n).encode()).hexdigest())
    original_filename = factory.Sequence(lambda n: f"invoice-{n}.pdf")
    mime = "application/pdf"
    size_bytes = 1234
    page_count = 1
