from dataclasses import dataclass
from typing import List

from ..service.order_service import OrderService
from ..domain.entities import Order, OrderStatus


@dataclass
class OrderItemResponse:
    product_id: int
    product_name: str
    quantity: int
    unit_price: str
    total_price: str


@dataclass
class OrderResponse:
    id: int
    user_id: int
    status: str
    items: List[OrderItemResponse]
    total_amount: str
    created_at: str

    @classmethod
    def from_entity(cls, order: Order) -> "OrderResponse":
        items = [
            OrderItemResponse(
                product_id=item.product_id,
                product_name=item.product_name,
                quantity=item.quantity,
                unit_price=str(item.unit_price),
                total_price=str(item.total_price),
            )
            for item in order.items
        ]
        return cls(
            id=order.id,
            user_id=order.user_id,
            status=order.status.value,
            items=items,
            total_amount=str(order.total_amount),
            created_at=order.created_at.isoformat(),
        )


@dataclass
class AddItemRequest:
    product_id: int
    quantity: int


class OrderAPI:
    def __init__(self, order_service: OrderService):
        self.order_service = order_service

    def create_order(self, user_id: int) -> OrderResponse:
        order = self.order_service.create_order(user_id)
        return OrderResponse.from_entity(order)

    def get_order(self, order_id: int) -> OrderResponse:
        order = self.order_service.get_order_by_id(order_id)
        return OrderResponse.from_entity(order)

    def list_orders(self, limit: int = 100, offset: int = 0) -> List[OrderResponse]:
        orders = self.order_service.list_orders(limit, offset)
        return [OrderResponse.from_entity(o) for o in orders]

    def list_user_orders(self, user_id: int) -> List[OrderResponse]:
        orders = self.order_service.list_user_orders(user_id)
        return [OrderResponse.from_entity(o) for o in orders]

    def list_pending_orders(self) -> List[OrderResponse]:
        orders = self.order_service.list_orders_by_status(OrderStatus.PENDING)
        return [OrderResponse.from_entity(o) for o in orders]

    def add_item(self, order_id: int, request: AddItemRequest) -> OrderResponse:
        order = self.order_service.add_item_to_order(
            order_id=order_id,
            product_id=request.product_id,
            quantity=request.quantity,
        )
        return OrderResponse.from_entity(order)

    def remove_item(self, order_id: int, product_id: int) -> OrderResponse:
        order = self.order_service.remove_item_from_order(order_id, product_id)
        return OrderResponse.from_entity(order)

    def confirm_order(self, order_id: int) -> OrderResponse:
        order = self.order_service.confirm_order(order_id)
        return OrderResponse.from_entity(order)

    def ship_order(self, order_id: int) -> OrderResponse:
        order = self.order_service.ship_order(order_id)
        return OrderResponse.from_entity(order)

    def deliver_order(self, order_id: int) -> OrderResponse:
        order = self.order_service.deliver_order(order_id)
        return OrderResponse.from_entity(order)

    def cancel_order(self, order_id: int) -> OrderResponse:
        order = self.order_service.cancel_order(order_id)
        return OrderResponse.from_entity(order)

    def delete_order(self, order_id: int) -> bool:
        return self.order_service.delete_order(order_id)
