from dataclasses import dataclass
from typing import List, Optional
from decimal import Decimal

from ..service.product_service import ProductService
from ..domain.entities import Product


@dataclass
class ProductResponse:
    id: int
    name: str
    description: str
    price: str
    stock_quantity: int
    is_available: bool

    @classmethod
    def from_entity(cls, product: Product) -> "ProductResponse":
        return cls(
            id=product.id,
            name=product.name,
            description=product.description,
            price=str(product.price),
            stock_quantity=product.stock_quantity,
            is_available=product.is_available,
        )


@dataclass
class CreateProductRequest:
    name: str
    description: str
    price: Decimal
    stock_quantity: int = 0


@dataclass
class UpdateProductRequest:
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    is_available: Optional[bool] = None


class ProductAPI:
    def __init__(self, product_service: ProductService):
        self.product_service = product_service

    def create_product(self, request: CreateProductRequest) -> ProductResponse:
        product = self.product_service.create_product(
            name=request.name,
            description=request.description,
            price=request.price,
            stock_quantity=request.stock_quantity,
        )
        return ProductResponse.from_entity(product)

    def get_product(self, product_id: int) -> ProductResponse:
        product = self.product_service.get_product_by_id(product_id)
        return ProductResponse.from_entity(product)

    def list_products(self, limit: int = 100, offset: int = 0) -> List[ProductResponse]:
        products = self.product_service.list_products(limit, offset)
        return [ProductResponse.from_entity(p) for p in products]

    def list_available_products(self) -> List[ProductResponse]:
        products = self.product_service.list_available_products()
        return [ProductResponse.from_entity(p) for p in products]

    def search_products(self, name: str) -> List[ProductResponse]:
        products = self.product_service.search_products(name)
        return [ProductResponse.from_entity(p) for p in products]

    def update_product(
        self, product_id: int, request: UpdateProductRequest
    ) -> ProductResponse:
        product = self.product_service.update_product(
            product_id=product_id,
            name=request.name,
            description=request.description,
            price=request.price,
            is_available=request.is_available,
        )
        return ProductResponse.from_entity(product)

    def add_stock(self, product_id: int, quantity: int) -> ProductResponse:
        product = self.product_service.add_stock(product_id, quantity)
        return ProductResponse.from_entity(product)

    def delete_product(self, product_id: int) -> bool:
        return self.product_service.delete_product(product_id)
