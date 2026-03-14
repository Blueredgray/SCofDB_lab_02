"""Репозитории для работы с БД."""
from __future__ import annotations

from uuid import UUID
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime

from app.domain.user import User
from app.domain.order import Order, OrderItem, OrderStatus, OrderStatusChange


class UserRepository:
    """Репозиторий пользователей."""
    
    def __init__(self, session: AsyncSession) -> None:
        """Инициализация репозитория."""
        self.session = session
    
    async def save(self, user: User) -> None:
        """Сохранить пользователя."""
        await self.session.execute(
            text("""
                INSERT INTO users (id, email, name, created_at)
                VALUES (:id, :email, :name, :created_at)
                ON CONFLICT (id) DO UPDATE SET
                    email = EXCLUDED.email,
                    name = EXCLUDED.name
            """),
            {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "created_at": user.created_at
            }
        )
        await self.session.commit()
    
    async def find_by_id(self, user_id: UUID) -> Optional[User]:
        """Найти пользователя по ID."""
        result = await self.session.execute(
            text("SELECT id, email, name, created_at FROM users WHERE id = :id"),
            {"id": user_id}
        )
        row = result.fetchone()
        if not row:
            return None
        return User(
            id=row[0],
            email=row[1],
            name=row[2],
            created_at=row[3]
        )
    
    async def find_by_email(self, email: str) -> Optional[User]:
        """Найти пользователя по email."""
        result = await self.session.execute(
            text("SELECT id, email, name, created_at FROM users WHERE email = :email"),
            {"email": email}
        )
        row = result.fetchone()
        if not row:
            return None
        return User(
            id=row[0],
            email=row[1],
            name=row[2],
            created_at=row[3]
        )
    
    async def find_all(self) -> List[User]:
        """Получить всех пользователей."""
        result = await self.session.execute(
            text("SELECT id, email, name, created_at FROM users ORDER BY created_at")
        )
        rows = result.fetchall()
        return [
            User(id=row[0], email=row[1], name=row[2], created_at=row[3])
            for row in rows
        ]


class OrderRepository:
    """Репозиторий заказов."""
    
    def __init__(self, session: AsyncSession) -> None:
        """Инициализация репозитория."""
        self.session = session
    
    async def save(self, order: Order) -> None:
        """Сохранить заказ с товарами и историей."""
        # Сохраняем заказ
        await self.session.execute(
            text("""
                INSERT INTO orders (id, user_id, status, total_amount, created_at)
                VALUES (:id, :user_id, :status, :total_amount, :created_at)
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    total_amount = EXCLUDED.total_amount
            """),
            {
                "id": order.id,
                "user_id": order.user_id,
                "status": order.status.value,
                "total_amount": order.total_amount,
                "created_at": order.created_at
            }
        )
        
        # Удаляем старые товары и сохраняем новые
        await self.session.execute(
            text("DELETE FROM order_items WHERE order_id = :order_id"),
            {"order_id": order.id}
        )
        
        for item in order.items:
            await self.session.execute(
                text("""
                    INSERT INTO order_items (id, order_id, product_name, price, quantity)
                    VALUES (:id, :order_id, :product_name, :price, :quantity)
                """),
                {
                    "id": item.id,
                    "order_id": order.id,
                    "product_name": item.product_name,
                    "price": item.price,
                    "quantity": item.quantity
                }
            )
        
        await self.session.commit()
    
    async def find_by_id(self, order_id: UUID) -> Optional[Order]:
        """Найти заказ по ID со всеми данными."""
        # Загружаем заказ
        result = await self.session.execute(
            text("SELECT id, user_id, status, total_amount, created_at FROM orders WHERE id = :id"),
            {"id": order_id}
        )
        row = result.fetchone()
        if not row:
            return None
        
        order = Order(
            id=row[0],
            user_id=row[1],
            status=OrderStatus(row[2]),
            total_amount=row[3],
            created_at=row[4]
        )
        
        # Загружаем товары
        items_result = await self.session.execute(
            text("SELECT id, product_name, price, quantity FROM order_items WHERE order_id = :order_id"),
            {"order_id": order_id}
        )
        for item_row in items_result.fetchall():
            order.items.append(OrderItem(
                id=item_row[0],
                product_name=item_row[1],
                price=item_row[2],
                quantity=item_row[3]
            ))
        
        # Загружаем историю статусов
        history_result = await self.session.execute(
            text("SELECT status, created_at FROM order_status_history WHERE order_id = :order_id ORDER BY created_at"),
            {"order_id": order_id}
        )
        order.status_history = [
            OrderStatusChange(status=OrderStatus(h[0]), created_at=h[1])
            for h in history_result.fetchall()
        ]
        
        return order
    
    async def find_by_user(self, user_id: UUID) -> List[Order]:
        """Найти заказы пользователя."""
        result = await self.session.execute(
            text("SELECT id FROM orders WHERE user_id = :user_id ORDER BY created_at DESC"),
            {"user_id": user_id}
        )
        order_ids = [row[0] for row in result.fetchall()]
        
        orders = []
        for oid in order_ids:
            order = await self.find_by_id(oid)
            if order:
                orders.append(order)
        return orders
    
    async def find_all(self) -> List[Order]:
        """Получить все заказы."""
        result = await self.session.execute(
            text("SELECT id FROM orders ORDER BY created_at DESC")
        )
        order_ids = [row[0] for row in result.fetchall()]
        
        orders = []
        for oid in order_ids:
            order = await self.find_by_id(oid)
            if order:
                orders.append(order)
        return orders