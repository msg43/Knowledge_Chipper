"""Utilities package for the Knowledge System."""

# Import only the cache management for now to avoid circular import issues
try:
    from .cache_management import clear_python_cache, should_clear_cache_on_startup
    __all__ = ["clear_python_cache", "should_clear_cache_on_startup"]
except ImportError:
    __all__ = []
