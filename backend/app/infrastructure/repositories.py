"""Repositories for data access."""
import uuid
from typing import Optional, List
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.user import User
from app.domain.order import Order, OrderItem, OrderStatus, OrderStatusChange
from app.domain.exceptions import UserNotFoundError, OrderNotFoundError


class UserRepository:
    """Repository for user operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, user: User) -> User:
        """Save user to DB."""
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
        return user

    async def find_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """Find user by ID."""
        result = await self.session.execute(
            text("SELECT id, email, name, created_at FROM users WHERE id = :id"),
            {"id": user_id}
        )
        row = result.fetchone()
        if row:
            return User(
                id=row[0],
                email=row[1],
                name=row[2],
                created_at=row[3]
            )
        return None

    async def find_by_email(self, email: str) -> Optional[User]:
        """Find user by email."""
        result = await self.session.execute(
            text("SELECT id, email, name, created_at FROM users WHERE email = :email"),
            {"email": email}
        )
        row = result.fetchone()
        if row:
            return User(
                id=row[0],
                email=row[1],
                name=row[2],
                created_at=row[3]
            )
        return None

    async def find_all(self) -> List[User]:
        """Get all users."""
        result = await self.session.execute(
            text("SELECT id, email, name, created_at FROM users ORDER BY created_at DESC")
        )
        rows = result.fetchall()
        return [
            User(id=row[0], email=row[1], name=row[2], created_at=row[3])
            for row in rows
        ]


class OrderRepository:
    """Repository for order operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, order: Order) -> Order:
        """Save order with items and history."""
        # Save order
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

        # Save items (delete old first)
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

        return order

    async def find_by_id(self, order_id: uuid.UUID) -> Optional[Order]:
        """Find order by ID with items and history."""
        # Get order
        result = await self.session.execute(
            text("""
                SELECT id, user_id, status, total_amount, created_at 
                FROM orders 
                WHERE id = :id
            """),
            {"id": order_id}
        )
        row = result.fetchone()
        if not row:
            return None

        order = Order(
            id=row[0],
            user_id=row[1],
            status=OrderStatus(row[2]),
            total_amount=float(row[3]),
            created_at=row[4],
            items=[],
            status_history=[]
        )

        # Get items
        items_result = await self.session.execute(
            text("""
                SELECT id, product_name, price, quantity
                FROM order_items
                WHERE order_id = :order_id
            """),
            {"order_id": order_id}
        )
        for item_row in items_result.fetchall():
            order.items.append(OrderItem(
                id=item_row[0],
                product_name=item_row[1],
                price=float(item_row[2]),
                quantity=item_row[3]
            ))

        # Get history
        history_result = await self.session.execute(
            text("""
                SELECT id, status, changed_at
                FROM order_status_history
                WHERE order_id = :order_id
                ORDER BY changed_at
            """),
            {"order_id": order_id}
        )
        for hist_row in history_result.fetchall():
            order.status_history.append(OrderStatusChange(
                id=hist_row[0],
                status=hist_row[1],
                changed_at=hist_row[2]
            ))

        return order

    async def find_by_user(self, user_id: uuid.UUID) -> List[Order]:
        """Find orders by user ID."""
        result = await self.session.execute(
            text("SELECT id FROM orders WHERE user_id = :user_id ORDER BY created_at DESC"),
            {"user_id": user_id}
        )
        orders = []
        for row in result.fetchall():
            order = await self.find_by_id(row[0])
            if order:
                orders.append(order)
        return orders

    async def find_all(self) -> List[Order]:
        """Get all orders."""
        result = await self.session.execute(
            text("SELECT id FROM orders ORDER BY created_at DESC")
        )
        orders = []
        for row in result.fetchall():
            order = await self.find_by_id(row[0])
            if order:
                orders.append(order)
        return orders
