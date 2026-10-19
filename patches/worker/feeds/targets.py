"""Enabled destination matrix for Homesector feed generation."""
FEED_TARGETS = {
    "google": ("BG", "RO", "GR", "HU"),
    "meta": ("BG", "RO", "GR", "HU"),
    "favi": ("BG", "RO", "GR", "HU"),
    "biano": ("BG",),
}

def targets():
    return [(channel, market) for channel, markets in FEED_TARGETS.items() for market in markets]

def enabled(channel, market):
    return market in FEED_TARGETS.get(channel, ())
