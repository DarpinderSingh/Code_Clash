from datetime import datetime, timezone
from typing import Optional, Dict, Any


def parse_int_field(value: Any, field_name: str, min_val: Optional[int] = None, max_val: Optional[int] = None) -> int:
    try:
        val = int(value)
    except (ValueError, TypeError):
        raise ValueError(f"{field_name} must be a valid integer")
    if min_val is not None and val < min_val:
        raise ValueError(f"{field_name} cannot be less than {min_val}")
    if max_val is not None and val > max_val:
        raise ValueError(f"{field_name} cannot be greater than {max_val}")
    return val


def parse_datetime_field(value: Any, field_name: str) -> datetime:
    if not value or not str(value).strip():
        raise ValueError(f"{field_name} is required")
    text = str(value).strip()
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        try:
            # Fallback for HTML5 datetime-local format: YYYY-MM-DDTHH:MM
            dt = datetime.strptime(text, "%Y-%m-%dT%H:%M")
        except Exception:
            raise ValueError(f"Invalid datetime format for {field_name}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
