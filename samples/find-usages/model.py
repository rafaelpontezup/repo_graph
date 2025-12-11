from dataclasses import dataclass


@dataclass
class User:
    name: str
    email: str
    age: int


@dataclass
class Product:
    title: str
    price: float
