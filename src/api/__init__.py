"""FastAPI REST API for the Cloud Migration Agent Platform."""
try:
    from .routes import router
    __all__ = ["router"]
except ImportError:
    pass
