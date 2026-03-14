"""Сервис для работы с заказами."""
from __future__ import annotations

from uuid import UUID
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.order import Order, OrderItem, OrderStatus, OrderStatusChange
from app.infrastructure.repositories import OrderRepository


class OrderService:
    """Сервис для управления заказами."""
    
    def __init__(self, session: AsyncSession) -> None:
        """Инициализация сервиса."""
        self.session = session
        self.repo = OrderRepository(session)
    
    async def create_order(self, user_id: UUID) -> Order:
        """Создать новый заказ."""
        order = Order(user_id=user_id)
        await self.repo.save(order)
        return order
    
    async def get_order(self, order_id: UUID) -> Optional[Order]:
        """Получить заказ по ID."""
        return await self.repo.find_by_id(order_id)
    
    async def add_item(self, order_id: UUID, product_name: str, price: Decimal, quantity: int) -> Order:
        """Добавить товар в заказ."""
        order = await self.repo.find_by_id(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        
        item = OrderItem(product_name=product_name, price=price, quantity=quantity)
        order.add_item(item)
        await self.repo.save(order)
        return order
    
    async def pay_order(self, order_id: UUID) -> Order:
        """Оплатить заказ."""
        order = await self.repo.find_by_id(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        
        order.pay()
        await self.repo.save(order)
        return order
    
    async def cancel_order(self, order_id: UUID) -> Order:
        """Отменить заказ."""
        order = await self.repo.find_by_id(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        
        order.cancel()
        await self.repo.save(order)
        return order
    
    async def ship_order(self, order_id: UUID) -> Order:
        """Отправить заказ."""
        order = await self.repo.find_by_id(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        
        order.ship()
        await self.repo.save(order)
        return order
    
    async def complete_order(self, order_id: UUID) -> Order:
        """Завершить заказ."""
        order = await self.repo.find_by_id(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        
        order.complete()
        await self.repo.save(order)
        return order
    
    async def list_orders(self) -> List[Order]:
        """Получить список всех заказов."""
        return await self.repo.find_all()
    
    async def get_order_history(self, order_id: UUID) -> List[OrderStatusChange]:
        """Получить историю статусов заказа."""
        order = await self.repo.find_by_id(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        return order.status_history