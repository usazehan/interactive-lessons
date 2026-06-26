"""Test package.

Force an in-memory database before any app module is imported so the test
suite never touches the real database file. This runs first during test
discovery, ahead of the individual test modules.
"""
import os

os.environ.setdefault("DATABASE_PATH", ":memory:")
