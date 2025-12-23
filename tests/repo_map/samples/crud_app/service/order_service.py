from typing import List
from decimal import Decimal

from ..domain.entities import Order, OrderItem, OrderStatus
from ..domain.exceptions import ValidationError, NotFoundError
from ..repository.order_repository import OrderRepository
from .product_service import ProductService
from .user_service import UserService


class OrderService:
    def __init__(
        self,
        order_repository: OrderRepository,
        user_service: UserService,
        product_service: ProductService,
    ):
        self.order_repository = order_repository
        self.user_service = user_service
        self.product_service = product_service

    def create_order(self, user_id: int) -> Order:
        self.user_service.get_user_by_id(user_id)

        order = Order(user_id=user_id, status=OrderStatus.PENDING)
        return self.order_repository.save(order)

    def get_order_by_id(self, order_id: int) -> Order:
        order = self.order_repository.find_by_id(order_id)
        if not order:
            raise NotFoundError("Order", order_id)
        return order

    def list_orders(self, limit: int = 100, offset: int = 0) -> List[Order]:
        return self.order_repository.find_all(limit, offset)

    def list_user_orders(self, user_id: int) -> List[Order]:
        self.user_service.get_user_by_id(user_id)
        return self.order_repository.find_by_user_id(user_id)

    def list_orders_by_status(self, status: OrderStatus) -> List[Order]:
        return self.order_repository.find_by_status(status)

    def add_item_to_order(
        self,
        order_id: int,
        product_id: int,
        quantity: int,
    ) -> Order:
        if quantity <= 0:
            raise ValidationError(["Quantity must be positive"])

        order = self.get_order_by_id(order_id)

        if order.status != OrderStatus.PENDING:
            raise ValidationError(["Cannot modify non-pending order"])

        product = self.product_service.get_product_by_id(product_id)

        if not product.is_in_stock():
            raise ValidationError([f"Product '{product.name}' is not available"])

        if quantity > product.stock_quantity:
            raise ValidationError(
                [f"Insufficient stock for '{product.name}'. Available: {product.stock_quantity}"]
            )

        item = OrderItem(
            product_id=product.id,
            product_name=product.name,
            quantity=quantity,
            unit_price=product.price,
        )

        order.add_item(item)
        return self.order_repository.save(order)

    def remove_item_from_order(self, order_id: int, product_id: int) -> Order:
        order = self.get_order_by_id(order_id)

        if order.status != OrderStatus.PENDING:
            raise ValidationError(["Cannot modify non-pending order"])

        order.remove_item(product_id)
        return self.order_repository.save(order)

    def confirm_order(self, order_id: int) -> Order:
        order = self.get_order_by_id(order_id)

        errors = order.validate()
        if errors:
            raise ValidationError(errors)

        for item in order.items:
            product = self.product_service.get_product_by_id(item.product_id)
            if item.quantity > product.stock_quantity:
                raise ValidationError(
                    [f"Insufficient stock for '{item.product_name}'"]
                )

        for item in order.items:
            self.product_service.remove_stock(item.product_id, item.quantity)

        order.confirm()
        return self.order_repository.save(order)

    def ship_order(self, order_id: int) -> Order:
        order = self.get_order_by_id(order_id)
        order.ship()
        return self.order_repository.save(order)

    def deliver_order(self, order_id: int) -> Order:
        order = self.get_order_by_id(order_id)
        order.deliver()
        return self.order_repository.save(order)

    def cancel_order(self, order_id: int) -> Order:
        order = self.get_order_by_id(order_id)

        if order.status == OrderStatus.CONFIRMED:
            for item in order.items:
                self.product_service.add_stock(item.product_id, item.quantity)

        order.cancel()
        return self.order_repository.save(order)

    def delete_order(self, order_id: int) -> bool:
        order = self.get_order_by_id(order_id)

        if order.status not in [OrderStatus.PENDING, OrderStatus.CANCELLED]:
            raise ValidationError(["Can only delete pending or cancelled orders"])

        return self.order_repository.delete(order_id)

    def calculate_order_total(self, order_id: int) -> Decimal:
        order = self.get_order_by_id(order_id)
        return order.total_amount

    def count_orders(self) -> int:
        return self.order_repository.count()

    def count_orders_by_status(self, status: OrderStatus) -> int:
        return self.order_repository.count_by_status(status)
