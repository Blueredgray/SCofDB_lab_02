"""Order service for managing orders."""
import uuid
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.order import Order, OrderItem, OrderStatus, OrderStatusChange
from app.domain.exceptions import OrderNotFoundError, OrderAlreadyPaidError
from app.infrastructure.repositories import OrderRepository


class OrderService:
    """Service for order operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = OrderRepository(session)

    async def create_order(self, user_id: uuid.UUID) -> Order:
        """Create new order for user."""
        order = Order(user_id=user_id)
        await self.repo.save(order)
        return order

    async def add_item(self, order_id: uuid.UUID, product_name: str, price: float, quantity: int) -> Order:
        """Add item to order."""
        order = await self.repo.find_by_id(order_id)
        if not order:
            raise OrderNotFoundError(order_id)

        item = OrderItem(product_name=product_name, price=price, quantity=quantity)
        order.add_item(item)
        await self.repo.save(order)
        return order

    async def pay_order(self, order_id: uuid.UUID) -> Order:
        """Pay order - uses domain logic."""
        order = await self.repo.find_by_id(order_id)
        if not order:
            raise OrderNotFoundError(order_id)

        order.pay()
        await self.repo.save(order)
        return order

    async def cancel_order(self, order_id: uuid.UUID) -> Order:
        """Cancel order."""
        order = await self.repo.find_by_id(order_id)
        if not order:
            raise OrderNotFoundError(order_id)

        order.cancel()
        await self.repo.save(order)
        return order

    async def ship_order(self, order_id: uuid.UUID) -> Order:
        """Ship order."""
        order = await self.repo.find_by_id(order_id)
        if not order:
            raise OrderNotFoundError(order_id)

        order.ship()
        await self.repo.save(order)
        return order

    async def complete_order(self, order_id: uuid.UUID) -> Order:
        """Complete order."""
        order = await self.repo.find_by_id(order_id)
        if not order:
            raise OrderNotFoundError(order_id)

        order.complete()
        await self.repo.save(order)
        return order

    async def list_orders(self) -> List[Order]:
        """List all orders."""
        return await self.repo.find_all()

    async def get_order_history(self, order_id: uuid.UUID) -> List[OrderStatusChange]:
        """Get order status history."""
        order = await self.repo.find_by_id(order_id)
        if not order:
            raise OrderNotFoundError(order_id)
        return order.status_history
