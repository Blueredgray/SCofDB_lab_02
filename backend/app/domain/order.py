"""Доменная модель заказа."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4
from datetime import datetime
from typing import List

from app.domain.exceptions import OrderAlreadyPaidError


class OrderStatus(str, Enum):
    """Статусы заказа."""
    CREATED = "created"
    PAID = "paid"
    CANCELLED = "cancelled"
    SHIPPED = "shipped"
    COMPLETED = "completed"


@dataclass
class OrderItem:
    """Позиция заказа."""
    
    product_name: str
    price: Decimal
    quantity: int
    id: UUID = field(default_factory=uuid4)
    
    def __post_init__(self) -> None:
        """Валидация цены и количества."""
        if self.price < 0:
            raise ValueError("Price cannot be negative")
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive")
    
    @property
    def subtotal(self) -> Decimal:
        """Стоимость позиции."""
        return self.price * self.quantity


@dataclass
class OrderStatusChange:
    """Запись об изменении статуса заказа."""
    
    status: OrderStatus
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Order:
    """Заказ пользователя."""
    
    user_id: UUID
    id: UUID = field(default_factory=uuid4)
    status: OrderStatus = field(default=OrderStatus.CREATED)
    total_amount: Decimal = field(default=Decimal("0.00"))
    created_at: datetime = field(default_factory=datetime.utcnow)
    items: List[OrderItem] = field(default_factory=list)
    status_history: List[OrderStatusChange] = field(default_factory=list)
    
    def __post_init__(self) -> None:
        """Инициализация истории статусов."""
        if not self.status_history:
            self.status_history.append(OrderStatusChange(self.status))
    
    def add_item(self, product_name: str, price: Decimal, quantity: int) -> None:
        """Добавить товар в заказ.
        
        Args:
            product_name: Название товара
            price: Цена товара
            quantity: Количество
        """
        item = OrderItem(product_name=product_name, price=price, quantity=quantity)
        self.items.append(item)
        self._recalculate_total()
    
    def _recalculate_total(self) -> None:
        """Пересчитать общую сумму заказа."""
        self.total_amount = sum(item.subtotal for item in self.items)
    
    def pay(self) -> None:
        """Оплатить заказ. Нельзя оплатить дважды!"""
        if self.status == OrderStatus.PAID:
            raise OrderAlreadyPaidError(order_id=self.id)
        if self.status != OrderStatus.CREATED:
            raise ValueError(f"Cannot pay order with status {self.status}")
        self.status = OrderStatus.PAID
        self.status_history.append(OrderStatusChange(self.status))
    
    def cancel(self) -> None:
        """Отменить заказ."""
        if self.status == OrderStatus.PAID:
            raise OrderAlreadyPaidError(order_id=self.id, message=f"Cannot cancel paid order {self.id}")
        if self.status not in [OrderStatus.CREATED, OrderStatus.PAID]:
            raise ValueError(f"Cannot cancel order with status {self.status}")
        self.status = OrderStatus.CANCELLED
        self.status_history.append(OrderStatusChange(self.status))
    
    def ship(self) -> None:
        """Отправить заказ."""
        if self.status != OrderStatus.PAID:
            raise ValueError(f"Cannot ship order with status {self.status}")
        self.status = OrderStatus.SHIPPED
        self.status_history.append(OrderStatusChange(self.status))
    
    def complete(self) -> None:
        """Завершить заказ."""
        if self.status != OrderStatus.SHIPPED:
            raise ValueError(f"Cannot complete order with status {self.status}")
        self.status = OrderStatus.COMPLETED
        self.status_history.append(OrderStatusChange(self.status))