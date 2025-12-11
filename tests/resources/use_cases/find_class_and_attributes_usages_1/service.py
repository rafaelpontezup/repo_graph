from model import User, Product


def get_user_email(user: User) -> str:
    """Retorna o email do usuário."""
    return user.email


def create_user(name: str, email: str) -> User:
    """Cria um novo usuário."""
    user = User(name=name, email=email, age=0)
    print(f"Created user: {user.name}")
    return user


def send_notification(user: User, message: str) -> None:
    """Envia notificação para o usuário."""
    print(f"Sending to {user.email}: {message}")


def process_order(user: User, product: Product) -> None:
    """Processa um pedido."""
    print(f"Order for {user.name}: {product.title} - ${product.price}")
    send_notification(user, f"Your order for {product.title} is confirmed!")
