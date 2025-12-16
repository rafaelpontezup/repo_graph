from typing import List, Optional
from datetime import datetime
from decimal import Decimal

from .base import BaseRepository
from ..domain.entities import Order, OrderItem, OrderStatus


class OrderRepository(BaseRepository[Order]):
    def find_by_id(self, order_id: int) -> Optional[Order]:
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, user_id, status, created_at, updated_at
                FROM orders
                WHERE id = ?
                """,
                (order_id,),
            )
            row = cursor.fetchone()
            if row:
                order = self._row_to_entity(row)
                order.items = self._find_items_by_order_id(conn, order.id)
                return order
            return None

    def find_all(self, limit: int = 100, offset: int = 0) -> List[Order]:
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, user_id, status, created_at, updated_at
                FROM orders
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            orders = []
            for row in cursor.fetchall():
                order = self._row_to_entity(row)
                order.items = self._find_items_by_order_id(conn, order.id)
                orders.append(order)
            return orders

    def find_by_user_id(self, user_id: int) -> List[Order]:
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, user_id, status, created_at, updated_at
                FROM orders
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            orders = []
            for row in cursor.fetchall():
                order = self._row_to_entity(row)
                order.items = self._find_items_by_order_id(conn, order.id)
                orders.append(order)
            return orders

    def find_by_status(self, status: OrderStatus) -> List[Order]:
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, user_id, status, created_at, updated_at
                FROM orders
                WHERE status = ?
                ORDER BY created_at DESC
                """,
                (status.value,),
            )
            orders = []
            for row in cursor.fetchall():
                order = self._row_to_entity(row)
                order.items = self._find_items_by_order_id(conn, order.id)
                orders.append(order)
            return orders

    def save(self, order: Order) -> Order:
        with self.get_connection() as conn:
            if order.id is None:
                cursor = conn.execute(
                    """
                    INSERT INTO orders (user_id, status, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (
                        order.user_id,
                        order.status.value,
                        order.created_at.isoformat(),
                    ),
                )
                order.id = cursor.lastrowid
            else:
                order.updated_at = datetime.now()
                conn.execute(
                    """
                    UPDATE orders
                    SET user_id = ?, status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        order.user_id,
                        order.status.value,
                        order.updated_at.isoformat(),
                        order.id,
                    ),
                )

            self._save_items(conn, order)
            return order

    def delete(self, order_id: int) -> bool:
        with self.get_connection() as conn:
            conn.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
            cursor = conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
            return cursor.rowcount > 0

    def count(self) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM orders")
            return cursor.fetchone()[0]

    def count_by_status(self, status: OrderStatus) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM orders WHERE status = ?", (status.value,)
            )
            return cursor.fetchone()[0]

    def _find_items_by_order_id(self, conn, order_id: int) -> List[OrderItem]:
        cursor = conn.execute(
            """
            SELECT id, order_id, product_id, product_name, quantity, unit_price
            FROM order_items
            WHERE order_id = ?
            """,
            (order_id,),
        )
        return [
            OrderItem(
                id=row["id"],
                order_id=row["order_id"],
                product_id=row["product_id"],
                product_name=row["product_name"],
                quantity=row["quantity"],
                unit_price=Decimal(row["unit_price"]),
            )
            for row in cursor.fetchall()
        ]

    def _save_items(self, conn, order: Order) -> None:
        conn.execute("DELETE FROM order_items WHERE order_id = ?", (order.id,))

        for item in order.items:
            item.order_id = order.id
            cursor = conn.execute(
                """
                INSERT INTO order_items 
                (order_id, product_id, product_name, quantity, unit_price)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    item.order_id,
                    item.product_id,
                    item.product_name,
                    item.quantity,
                    str(item.unit_price),
                ),
            )
            item.id = cursor.lastrowid

    def _row_to_entity(self, row) -> Order:
        return Order(
            id=row["id"],
            user_id=row["user_id"],
            status=OrderStatus(row["status"]),
            items=[],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=(
                datetime.fromisoformat(row["updated_at"])
                if row["updated_at"]
                else None
            ),
        )
