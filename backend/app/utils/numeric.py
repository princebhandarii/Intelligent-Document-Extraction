import re
from typing import Optional, Union


def parse_amount(raw: Optional[Union[str, int, float]]) -> Optional[float]:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)

    text = str(raw).strip()
    if not text:
        return None

    is_negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    text = re.sub(r"[^\d.,\-]", "", text)

    if text in ("", "-", ".", ","):
        return None

    has_comma = "," in text
    has_dot = "." in text

    if has_comma and has_dot:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif has_comma and not has_dot:
        comma_index = text.rfind(",")
        digits_after = len(text) - comma_index - 1
        if digits_after == 3:
            # e.g. "1,234" or "1,234,567" -> thousands separator(s)
            text = text.replace(",", "")
        else:
            # e.g. "17,45" -> decimal separator
            text = text.replace(",", ".")
    elif has_dot and not has_comma:
        dot_index = text.rfind(".")
        digits_after = len(text) - dot_index - 1
        if text.count(".") > 1 or digits_after == 3:
            # e.g. "1.234", "2.500", or "1.234.567" -> thousands separator(s)
            text = text.replace(".", "")
        # else: e.g. "138.9" -> already a valid decimal, leave as-is

    try:
        value = float(text)
    except ValueError:
        return None

    return -abs(value) if is_negative else value


def is_close(calculated: Optional[float], reported: Optional[float], tolerance_percent: float) -> bool:
    if calculated is None or reported is None:
        return False
    if reported == 0:
        return abs(calculated) <= max(tolerance_percent, 0.5)
    variance_percent = abs(calculated - reported) / abs(reported) * 100
    return variance_percent <= tolerance_percent