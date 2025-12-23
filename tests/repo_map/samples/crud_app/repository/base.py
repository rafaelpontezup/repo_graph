from abc import ABC, abstractmethod
from typing import TypeVar, Generic, List, Optional
import sqlite3
from contextlib import contextmanager

T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    def __init__(self, db_path: str = "database.db"):
        self.db_path = db_path

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @abstractmethod
    def find_by_id(self, entity_id: int) -> Optional[T]:
        pass

    @abstractmethod
    def find_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        pass

    @abstractmethod
    def save(self, entity: T) -> T:
        pass

    @abstractmethod
    def delete(self, entity_id: int) -> bool:
        pass

    @abstractmethod
    def count(self) -> int:
        pass
