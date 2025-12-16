from dataclasses import dataclass
from typing import List, Optional

from ..service.user_service import UserService
from ..domain.entities import User


@dataclass
class UserResponse:
    id: int
    name: str
    email: str
    status: str
    created_at: str

    @classmethod
    def from_entity(cls, user: User) -> "UserResponse":
        return cls(
            id=user.id,
            name=user.name,
            email=user.email,
            status=user.status.value,
            created_at=user.created_at.isoformat(),
        )


@dataclass
class CreateUserRequest:
    name: str
    email: str
    password: str


@dataclass
class UpdateUserRequest:
    name: Optional[str] = None
    email: Optional[str] = None


class UserAPI:
    def __init__(self, user_service: UserService):
        self.user_service = user_service

    def create_user(self, request: CreateUserRequest) -> UserResponse:
        user = self.user_service.create_user(
            name=request.name,
            email=request.email,
            password=request.password,
        )
        return UserResponse.from_entity(user)

    def get_user(self, user_id: int) -> UserResponse:
        user = self.user_service.get_user_by_id(user_id)
        return UserResponse.from_entity(user)

    def list_users(self, limit: int = 100, offset: int = 0) -> List[UserResponse]:
        users = self.user_service.list_users(limit, offset)
        return [UserResponse.from_entity(user) for user in users]

    def update_user(self, user_id: int, request: UpdateUserRequest) -> UserResponse:
        user = self.user_service.update_user(
            user_id=user_id,
            name=request.name,
            email=request.email,
        )
        return UserResponse.from_entity(user)

    def delete_user(self, user_id: int) -> bool:
        return self.user_service.delete_user(user_id)

    def activate_user(self, user_id: int) -> UserResponse:
        user = self.user_service.activate_user(user_id)
        return UserResponse.from_entity(user)

    def deactivate_user(self, user_id: int) -> UserResponse:
        user = self.user_service.deactivate_user(user_id)
        return UserResponse.from_entity(user)
