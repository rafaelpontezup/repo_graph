from model import User


class UserHandler:
    def __init__(self):
        self.users = []

    def add_user(self, user: User) -> None:
        self.users.append(user)
        print(f"Added: {user.name} ({user.email})")

    def find_by_email(self, email: str) -> User:
        for u in self.users:
            if u.email == email:
                return u
        return None

    def update_email(self, user: User, new_email: str) -> None:
        old = user.email
        user.email = new_email
        print(f"Updated email from {old} to {user.email}")
