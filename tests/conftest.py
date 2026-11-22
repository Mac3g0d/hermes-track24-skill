"""Load every fixture module as a pytest plugin."""

pytest_plugins = [
    "fixtures.markers",
    "fixtures.crypto",
    "fixtures.payloads",
    "fixtures.network",
    "fixtures.repository",
]
