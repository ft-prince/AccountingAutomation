from .base import *  # noqa: F403
from .base import REST_FRAMEWORK as _BASE_REST_FRAMEWORK

DEBUG = False
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Throttles are exercised by dedicated tests that override these; keep the suite unthrottled.
REST_FRAMEWORK = {
    **_BASE_REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {
        "upload": "100000/hour",
        "extraction": "100000/hour",
        "drafting": "100000/hour",
        "forecast": "100000/hour",
    },
}  # noqa: F405

# The suite stubs the Anthropic client shape, and must never depend on a developer's local
# .env choosing a provider. Groq is covered explicitly in apps/core/tests/test_llm.py.
LLM_PROVIDER = "anthropic"
GROQ_API_KEY = ""
