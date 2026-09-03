"""Per-org rate limits on the spend amplifiers. PROJECT_SPECS §12."""

from rest_framework.throttling import SimpleRateThrottle


class OrgRateThrottle(SimpleRateThrottle):
    scope = "org"

    def get_cache_key(self, request, view):  # type: ignore[no-untyped-def]
        org = getattr(request, "org", None)
        if org is None:
            return None
        return self.cache_format % {"scope": self.scope, "ident": str(org.pk)}


class UploadThrottle(OrgRateThrottle):
    scope = "upload"


class ExtractionThrottle(OrgRateThrottle):
    scope = "extraction"


class DraftingThrottle(OrgRateThrottle):
    scope = "drafting"


class ForecastThrottle(OrgRateThrottle):
    scope = "forecast"
