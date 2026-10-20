"""Keep physical stock separate from Homesector's supplier fulfilment policy.

The existing stock sync sets CONTINUE with no expected_arrival for supplier
stock, and CONTINUE with expected_arrival for a supplier replenishment.
Zero warehouse stock alone therefore does not imply a backorder.
"""
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

VALUES = {"in_stock", "out_of_stock", "preorder", "backorder"}


def feed_availability(row):
    explicit = row.get("availability")
    if explicit:
        if explicit not in VALUES:
            raise ValueError("Unsupported explicit availability")
        return explicit
    if row.get("available"):
        return "in_stock"
    if row.get("continue_selling"):
        if row.get("expected_arrival") or row.get("availability_date"):
            return "backorder"
        return "in_stock"
    return "out_of_stock"


def arrival_timestamp(value):
    """Convert Shopify's date to ISO 8601; never invent a replenishment date."""
    if not value:
        return None
    text = str(value).strip()
    try:
        if len(text) == 10:
            return datetime.combine(date.fromisoformat(text), time.min,
                                    tzinfo=ZoneInfo("Europe/Sofia")).isoformat()
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.isoformat() if parsed.tzinfo else text
    except ValueError:
        return text  # Retain source for the validator to flag; do not fabricate.
