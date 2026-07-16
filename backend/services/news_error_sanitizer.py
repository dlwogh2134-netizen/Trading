from __future__ import annotations

import re
from typing import Final


SENSITIVE_QUERY_VALUE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(\b(?:token|api_key|apikey|secret|client_secret)=)[^&\s\"']+",
    re.IGNORECASE,
)


def sanitize_external_error_message(error: Exception) -> str:
    return SENSITIVE_QUERY_VALUE_PATTERN.sub(r"\1[REDACTED]", str(error))
