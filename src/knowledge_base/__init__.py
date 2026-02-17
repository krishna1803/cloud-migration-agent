"""
Knowledge Base integration for Oracle 23ai Vector Database.
"""

from .kb_manager import KnowledgeBaseManager, kb_manager
from .collections import COLLECTIONS

__all__ = ["KnowledgeBaseManager", "kb_manager", "COLLECTIONS"]
