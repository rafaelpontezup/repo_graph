from typing import List
from decimal import Decimal

from ..domain.entities import Product
from ..domain.exceptions import ValidationError, NotFoundError
from ..repository.product_repository import ProductRepository


class ProductService:
    def __init__(self, repository: ProductRepository):
        self.repository = repository

    def create_product(
        self,
        name: str,
        description: str,
        price: Decimal,
        stock_quantity: int = 0,
    ) -> Product:
        product = Product(
            name=name,
            description=description,
            price=price,
            stock_quantity=stock_quantity,
            is_available=True,
        )

        errors = product.validate()
        if errors:
            raise ValidationError(errors)

        return self.repository.save(product)

    def get_product_by_id(self, product_id: int) -> Product:
        product = self.repository.find_by_id(product_id)
        if not product:
            raise NotFoundError("Product", product_id)
        return product

    def list_products(self, limit: int = 100, offset: int = 0) -> List[Product]:
        return self.repository.find_all(limit, offset)

    def list_available_products(self) -> List[Product]:
        return self.repository.find_available()

    def search_products(self, name: str) -> List[Product]:
        return self.repository.find_by_name(name)

    def update_product(
        self,
        product_id: int,
        name: str = None,
        description: str = None,
        price: Decimal = None,
        is_available: bool = None,
    ) -> Product:
        product = self.get_product_by_id(product_id)

        if name is not None:
            product.name = name
        if description is not None:
            product.description = description
        if price is not None:
            product.price = price
        if is_available is not None:
            product.is_available = is_available

        errors = product.validate()
        if errors:
            raise ValidationError(errors)

        return self.repository.save(product)

    def add_stock(self, product_id: int, quantity: int) -> Product:
        if quantity <= 0:
            raise ValidationError(["Quantity must be positive"])

        product = self.get_product_by_id(product_id)
        product.increase_stock(quantity)
        return self.repository.save(product)

    def remove_stock(self, product_id: int, quantity: int) -> Product:
        if quantity <= 0:
            raise ValidationError(["Quantity must be positive"])

        product = self.get_product_by_id(product_id)

        if quantity > product.stock_quantity:
            raise ValidationError(
                [f"Insufficient stock. Available: {product.stock_quantity}"]
            )

        product.decrease_stock(quantity)
        return self.repository.save(product)

    def delete_product(self, product_id: int) -> bool:
        self.get_product_by_id(product_id)
        return self.repository.delete(product_id)

    def count_products(self) -> int:
        return self.repository.count()
