from typing import List, Optional
from datetime import datetime

from .base import BaseRepository
from ..domain.entities import User, UserStatus


class UserRepository(BaseRepository[User]):
    def find_by_id(self, user_id: int) -> Optional[User]:
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, name, email, password_hash, status, created_at, updated_at
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_entity(row)
            return None

    def find_by_email(self, email: str) -> Optional[User]:
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, name, email, password_hash, status, created_at, updated_at
                FROM users
                WHERE email = ?
                """,
                (email,),
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_entity(row)
            return None

    def find_all(self, limit: int = 100, offset: int = 0) -> List[User]:
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, name, email, password_hash, status, created_at, updated_at
                FROM users
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            return [self._row_to_entity(row) for row in cursor.fetchall()]

    def find_by_status(self, status: UserStatus) -> List[User]:
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, name, email, password_hash, status, created_at, updated_at
                FROM users
                WHERE status = ?
                ORDER BY created_at DESC
                """,
                (status.value,),
            )
            return [self._row_to_entity(row) for row in cursor.fetchall()]

    def save(self, user: User) -> User:
        with self.get_connection() as conn:
            if user.id is None:
                cursor = conn.execute(
                    """
                    INSERT INTO users (name, email, password_hash, status, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        user.name,
                        user.email,
                        user.password_hash,
                        user.status.value,
                        user.created_at.isoformat(),
                    ),
                )
                user.id = cursor.lastrowid
            else:
                user.updated_at = datetime.now()
                conn.execute(
                    """
                    UPDATE users
                    SET name = ?, email = ?, password_hash = ?, status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        user.name,
                        user.email,
                        user.password_hash,
                        user.status.value,
                        user.updated_at.isoformat(),
                        user.id,
                    ),
                )
            return user

    def delete(self, user_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            return cursor.rowcount > 0

    def count(self) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM users")
            return cursor.fetchone()[0]

    def exists_by_email(self, email: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM users WHERE email = ? LIMIT 1", (email,)
            )
            return cursor.fetchone() is not None

    def _row_to_entity(self, row) -> User:
        return User(
            id=row["id"],
            name=row["name"],
            email=row["email"],
            password_hash=row["password_hash"],
            status=UserStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=(
                datetime.fromisoformat(row["updated_at"])
                if row["updated_at"]
                else None
            ),
        )
