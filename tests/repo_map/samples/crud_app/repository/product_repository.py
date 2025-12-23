from typing import List, Optional
from datetime import datetime
from decimal import Decimal

from .base import BaseRepository
from ..domain.entities import Product


class ProductRepository(BaseRepository[Product]):
    def find_by_id(self, product_id: int) -> Optional[Product]:
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, name, description, price, stock_quantity, 
                       is_available, created_at, updated_at
                FROM products
                WHERE id = ?
                """,
                (product_id,),
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_entity(row)
            return None

    def find_all(self, limit: int = 100, offset: int = 0) -> List[Product]:
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, name, description, price, stock_quantity,
                       is_available, created_at, updated_at
                FROM products
                ORDER BY name ASC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            return [self._row_to_entity(row) for row in cursor.fetchall()]

    def find_available(self) -> List[Product]:
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, name, description, price, stock_quantity,
                       is_available, created_at, updated_at
                FROM products
                WHERE is_available = 1 AND stock_quantity > 0
                ORDER BY name ASC
                """
            )
            return [self._row_to_entity(row) for row in cursor.fetchall()]

    def find_by_name(self, name: str) -> List[Product]:
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, name, description, price, stock_quantity,
                       is_available, created_at, updated_at
                FROM products
                WHERE name LIKE ?
                ORDER BY name ASC
                """,
                (f"%{name}%",),
            )
            return [self._row_to_entity(row) for row in cursor.fetchall()]

    def save(self, product: Product) -> Product:
        with self.get_connection() as conn:
            if product.id is None:
                cursor = conn.execute(
                    """
                    INSERT INTO products 
                    (name, description, price, stock_quantity, is_available, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        product.name,
                        product.description,
                        str(product.price),
                        product.stock_quantity,
                        1 if product.is_available else 0,
                        product.created_at.isoformat(),
                    ),
                )
                product.id = cursor.lastrowid
            else:
                product.updated_at = datetime.now()
                conn.execute(
                    """
                    UPDATE products
                    SET name = ?, description = ?, price = ?, stock_quantity = ?,
                        is_available = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        product.name,
                        product.description,
                        str(product.price),
                        product.stock_quantity,
                        1 if product.is_available else 0,
                        product.updated_at.isoformat(),
                        product.id,
                    ),
                )
            return product

    def delete(self, product_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
            return cursor.rowcount > 0

    def count(self) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM products")
            return cursor.fetchone()[0]

    def update_stock(self, product_id: int, quantity: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE products
                SET stock_quantity = stock_quantity + ?, updated_at = ?
                WHERE id = ?
                """,
                (quantity, datetime.now().isoformat(), product_id),
            )
            return cursor.rowcount > 0

    def _row_to_entity(self, row) -> Product:
        return Product(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            price=Decimal(row["price"]),
            stock_quantity=row["stock_quantity"],
            is_available=bool(row["is_available"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=(
                datetime.fromisoformat(row["updated_at"])
                if row["updated_at"]
                else None
            ),
        )
