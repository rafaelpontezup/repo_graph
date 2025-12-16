from typing import List, Optional
import hashlib
import secrets

from ..domain.entities import User, UserStatus
from ..domain.exceptions import ValidationError, NotFoundError
from ..repository.user_repository import UserRepository


class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def create_user(self, name: str, email: str, password: str) -> User:
        if self.repository.exists_by_email(email):
            raise ValidationError(["Email already registered"])

        password_hash = self._hash_password(password)
        user = User(
            name=name,
            email=email,
            password_hash=password_hash,
            status=UserStatus.ACTIVE,
        )

        errors = user.validate()
        if errors:
            raise ValidationError(errors)

        return self.repository.save(user)

    def get_user_by_id(self, user_id: int) -> User:
        user = self.repository.find_by_id(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        return user

    def get_user_by_email(self, email: str) -> Optional[User]:
        return self.repository.find_by_email(email)

    def list_users(self, limit: int = 100, offset: int = 0) -> List[User]:
        return self.repository.find_all(limit, offset)

    def list_active_users(self) -> List[User]:
        return self.repository.find_by_status(UserStatus.ACTIVE)

    def update_user(
        self,
        user_id: int,
        name: Optional[str] = None,
        email: Optional[str] = None,
    ) -> User:
        user = self.get_user_by_id(user_id)

        if name is not None:
            user.name = name
        if email is not None:
            if email != user.email and self.repository.exists_by_email(email):
                raise ValidationError(["Email already registered"])
            user.email = email

        errors = user.validate()
        if errors:
            raise ValidationError(errors)

        return self.repository.save(user)

    def change_password(
        self, user_id: int, old_password: str, new_password: str
    ) -> User:
        user = self.get_user_by_id(user_id)

        if not self._verify_password(old_password, user.password_hash):
            raise ValidationError(["Invalid current password"])

        if len(new_password) < 8:
            raise ValidationError(["Password must be at least 8 characters"])

        user.password_hash = self._hash_password(new_password)
        return self.repository.save(user)

    def activate_user(self, user_id: int) -> User:
        user = self.get_user_by_id(user_id)
        user.activate()
        return self.repository.save(user)

    def deactivate_user(self, user_id: int) -> User:
        user = self.get_user_by_id(user_id)
        user.deactivate()
        return self.repository.save(user)

    def block_user(self, user_id: int) -> User:
        user = self.get_user_by_id(user_id)
        user.block()
        return self.repository.save(user)

    def delete_user(self, user_id: int) -> bool:
        self.get_user_by_id(user_id)
        return self.repository.delete(user_id)

    def authenticate(self, email: str, password: str) -> Optional[User]:
        user = self.repository.find_by_email(email)
        if not user:
            return None
        if not user.is_active():
            return None
        if not self._verify_password(password, user.password_hash):
            return None
        return user

    def count_users(self) -> int:
        return self.repository.count()

    def _hash_password(self, password: str) -> str:
        salt = secrets.token_hex(16)
        hash_obj = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), 100000
        )
        return f"{salt}${hash_obj.hex()}"

    def _verify_password(self, password: str, password_hash: str) -> bool:
        try:
            salt, stored_hash = password_hash.split("$")
            hash_obj = hashlib.pbkdf2_hmac(
                "sha256", password.encode(), salt.encode(), 100000
            )
            return hash_obj.hex() == stored_hash
        except ValueError:
            return False
