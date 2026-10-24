"""Data access: SQL lives here and nowhere else."""

from ..db.database import Database
from .accounts import AccountRepository
from .chat import ChatRepository
from .documents import DocumentRepository, Snapshot


class Storage:
    """Every repository over one database, created once per app."""

    def __init__(self, db: Database):
        self.db = db
        self.documents = DocumentRepository(db)
        self.chat = ChatRepository(db)
        self.accounts = AccountRepository(db)

    @classmethod
    def from_env(cls) -> "Storage":
        return cls(Database.from_env())


__all__ = ["AccountRepository", "ChatRepository", "DocumentRepository", "Snapshot", "Storage"]
