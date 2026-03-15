"""
Admin API Endpoints.

Provides endpoints for system administration and monitoring.

Submodules:
    - health: System health and monitoring
    - users: User management
    - projects: Project management
    - proposals: Proposal management
    - settings: Settings and prompt management
    - analytics: RAG verification and analytics
"""

__all__ = ["health", "users", "projects", "proposals", "settings", "analytics"]

from app.api.v1.endpoints.admin import health
from app.api.v1.endpoints.admin import users
from app.api.v1.endpoints.admin import projects
from app.api.v1.endpoints.admin import proposals
from app.api.v1.endpoints.admin import settings
from app.api.v1.endpoints.admin import analytics
