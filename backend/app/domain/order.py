"""Order domain models with status management."""
import uuid
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import List
from .exceptions import (
    OrderAlreadyPaidError, 
    OrderCancelledError,
    InvalidQuantityError,
    InvalidPriceError
)


class OrderStatus(Enum):
    """Order status enum."""
    CREATED = "created"
    PAID = "paid"
    CANCELLED = "cancelled"
    SHIPPED = "shipped"
    COMPLETED = "completed"


@dataclass
class OrderItem:
    """Item in order with price and quantity."""

    product_name: str
    price: float
    quantity: int
    id: uuid.UUID = field(default_factory=uuid.uuid4)

    def __post_init__(self):
        """Validate price and quantity."""
        if self.price < 0:
            raise InvalidPriceError(self.price)
        if self.quantity <= 0:
            raise InvalidQuantityError(self.quantity)

    @property
    def total(self) -> float:
        """Calculate item total."""
        return self.price * self.quantity


@dataclass
class OrderStatusChange:
    """Record of status change."""

    status: str
    changed_at: datetime = field(default_factory=datetime.now)
    id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass
class Order:
    """Order aggregate root with business rules."""

    user_id: uuid.UUID
    status: OrderStatus = field(default=OrderStatus.CREATED)
    total_amount: float = field(default=0.0)
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=datetime.now)
    items: List[OrderItem] = field(default_factory=list)
    status_history: List[OrderStatusChange] = field(default_factory=list)

    def __post_init__(self):
        """Initialize status history."""
        if not self.status_history:
            self._add_status_history()

    def _add_status_history(self):
        """Add current status to history."""
        self.status_history.append(OrderStatusChange(status=self.status.value))

    def add_item(self, item: OrderItem):
        """Add item to order."""
        self.items.append(item)
        self._recalculate_total()

    def _recalculate_total(self):
        """Recalculate order total from items."""
        self.total_amount = sum(item.total for item in self.items)

    def pay(self):
        """Pay order - critical: cannot pay twice!"""
        if self.status == OrderStatus.PAID:
            raise OrderAlreadyPaidError(self.id)
        if self.status == OrderStatus.CANCELLED:
            raise OrderCancelledError(self.id)
        self.status = OrderStatus.PAID
        self._add_status_history()

    def cancel(self):
        """Cancel order."""
        if self.status == OrderStatus.PAID:
            raise OrderAlreadyPaidError(self.id)
        if self.status == OrderStatus.CANCELLED:
            return
        self.status = OrderStatus.CANCELLED
        self._add_status_history()

    def ship(self):
        """Ship order."""
        if self.status != OrderStatus.PAID:
            raise DomainException("Order must be paid before shipping")
        self.status = OrderStatus.SHIPPED
        self._add_status_history()

    def complete(self):
        """Complete order."""
        if self.status != OrderStatus.SHIPPED:
            raise DomainException("Order must be shipped before completion")
        self.status = OrderStatus.COMPLETED
        self._add_status_history()
