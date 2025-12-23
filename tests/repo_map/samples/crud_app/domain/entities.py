from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from enum import Enum


class UserStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"


class OrderStatus(Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


@dataclass
class User:
    id: Optional[int] = None
    name: str = ""
    email: str = ""
    password_hash: str = ""
    status: UserStatus = UserStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE

    def activate(self) -> None:
        self.status = UserStatus.ACTIVE
        self.updated_at = datetime.now()

    def deactivate(self) -> None:
        self.status = UserStatus.INACTIVE
        self.updated_at = datetime.now()

    def block(self) -> None:
        self.status = UserStatus.BLOCKED
        self.updated_at = datetime.now()

    def validate(self) -> List[str]:
        errors = []
        if not self.name or len(self.name) < 2:
            errors.append("Name must have at least 2 characters")
        if not self.email or "@" not in self.email:
            errors.append("Invalid email format")
        if not self.password_hash:
            errors.append("Password is required")
        return errors


@dataclass
class Product:
    id: Optional[int] = None
    name: str = ""
    description: str = ""
    price: Decimal = Decimal("0.00")
    stock_quantity: int = 0
    is_available: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

    def is_in_stock(self) -> bool:
        return self.stock_quantity > 0 and self.is_available

    def decrease_stock(self, quantity: int) -> None:
        if quantity > self.stock_quantity:
            raise ValueError("Insufficient stock")
        self.stock_quantity -= quantity
        self.updated_at = datetime.now()

    def increase_stock(self, quantity: int) -> None:
        self.stock_quantity += quantity
        self.updated_at = datetime.now()

    def validate(self) -> List[str]:
        errors = []
        if not self.name or len(self.name) < 3:
            errors.append("Product name must have at least 3 characters")
        if self.price <= 0:
            errors.append("Price must be greater than zero")
        if self.stock_quantity < 0:
            errors.append("Stock quantity cannot be negative")
        return errors


@dataclass
class OrderItem:
    id: Optional[int] = None
    order_id: Optional[int] = None
    product_id: int = 0
    product_name: str = ""
    quantity: int = 1
    unit_price: Decimal = Decimal("0.00")

    @property
    def total_price(self) -> Decimal:
        return self.unit_price * self.quantity


@dataclass
class Order:
    id: Optional[int] = None
    user_id: int = 0
    status: OrderStatus = OrderStatus.PENDING
    items: List[OrderItem] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

    @property
    def total_amount(self) -> Decimal:
        return sum(item.total_price for item in self.items)

    @property
    def total_items(self) -> int:
        return sum(item.quantity for item in self.items)

    def add_item(self, item: OrderItem) -> None:
        item.order_id = self.id
        self.items.append(item)
        self.updated_at = datetime.now()

    def remove_item(self, product_id: int) -> None:
        self.items = [item for item in self.items if item.product_id != product_id]
        self.updated_at = datetime.now()

    def confirm(self) -> None:
        if self.status != OrderStatus.PENDING:
            raise ValueError("Only pending orders can be confirmed")
        self.status = OrderStatus.CONFIRMED
        self.updated_at = datetime.now()

    def ship(self) -> None:
        if self.status != OrderStatus.CONFIRMED:
            raise ValueError("Only confirmed orders can be shipped")
        self.status = OrderStatus.SHIPPED
        self.updated_at = datetime.now()

    def deliver(self) -> None:
        if self.status != OrderStatus.SHIPPED:
            raise ValueError("Only shipped orders can be delivered")
        self.status = OrderStatus.DELIVERED
        self.updated_at = datetime.now()

    def cancel(self) -> None:
        if self.status in [OrderStatus.SHIPPED, OrderStatus.DELIVERED]:
            raise ValueError("Cannot cancel shipped or delivered orders")
        self.status = OrderStatus.CANCELLED
        self.updated_at = datetime.now()

    def validate(self) -> List[str]:
        errors = []
        if not self.user_id:
            errors.append("User ID is required")
        if not self.items:
            errors.append("Order must have at least one item")
        return errors
