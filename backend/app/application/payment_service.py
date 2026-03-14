"""Сервис платежей с демонстрацией race condition.

Модуль содержит два метода оплаты:
- pay_order_unsafe: демонстрирует проблему конкурентного доступа
- pay_order_safe: решает проблему через REPEATABLE READ + FOR UPDATE
"""
from __future__ import annotations

from uuid import UUID
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class OrderAlreadyPaidError(Exception):
    """Заказ уже оплачен."""
    pass


class PaymentService:
    """Сервис для обработки платежей с контролем конкурентности."""
    
    def __init__(self, session: AsyncSession) -> None:
        """Инициализация сервиса.
        
        Args:
            session: Асинхронная сессия SQLAlchemy
        """
        self.session = session

    async def pay_order_unsafe(self, order_id: UUID) -> dict:
        """Небезопасная оплата - демонстрирует race condition.
        
        Использует READ COMMITTED (по умолчанию) без блокировок.
        При конкурентных запросах возможна двойная оплата!
        
        Args:
            order_id: UUID заказа
            
        Returns:
            dict: Результат операции
            
        Raises:
            OrderAlreadyPaidError: Если заказ уже оплачен
        """
        # 1. Читаем статус без блокировки - тут начинается проблема
        result = await self.session.execute(
            text("SELECT status FROM orders WHERE id = :order_id"),
            {"order_id": order_id}
        )
        row = result.fetchone()
        if not row:
            raise ValueError(f"Order {order_id} not found")
        
        current_status = row[0]
        
        # 2. Проверяем статус
        if current_status != "created":
            raise OrderAlreadyPaidError(f"Order {order_id} already paid")
        
        # 3. Обновляем статус
        await self.session.execute(
            text("UPDATE orders SET status = 'paid' WHERE id = :order_id"),
            {"order_id": order_id}
        )
        
        # 4. Записываем в историю
        await self.session.execute(
            text("""
                INSERT INTO order_status_history (order_id, status, created_at)
                VALUES (:order_id, 'paid', :created_at)
            """),
            {"order_id": order_id, "created_at": datetime.utcnow()}
        )
        
        await self.session.commit()
        
        return {"order_id": str(order_id), "status": "paid", "method": "unsafe"}

    async def pay_order_safe(self, order_id: UUID) -> dict:
        """Безопасная оплата с защитой от race condition.
        
        Использует REPEATABLE READ + FOR UPDATE для блокировки строки.
        Гарантирует атомарность операции.
        
        Args:
            order_id: UUID заказа
            
        Returns:
            dict: Результат операции
            
        Raises:
            OrderAlreadyPaidError: Если заказ уже оплачен
        """
        # 1. Устанавливаем уровень изоляции REPEATABLE READ
        await self.session.execute(
            text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        )
        
        # 2. Блокируем строку FOR UPDATE - вторая транзакция ждёт здесь
        result = await self.session.execute(
            text("SELECT status FROM orders WHERE id = :order_id FOR UPDATE"),
            {"order_id": order_id}
        )
        row = result.fetchone()
        if not row:
            raise ValueError(f"Order {order_id} not found")
        
        current_status = row[0]
        
        # 3. Проверяем статус после блокировки
        if current_status != "created":
            raise OrderAlreadyPaidError(f"Order {order_id} already paid")
        
        # 4. Обновляем статус
        await self.session.execute(
            text("UPDATE orders SET status = 'paid' WHERE id = :order_id"),
            {"order_id": order_id}
        )
        
        # 5. Записываем в историю
        await self.session.execute(
            text("""
                INSERT INTO order_status_history (order_id, status, created_at)
                VALUES (:order_id, 'paid', :created_at)
            """),
            {"order_id": order_id, "created_at": datetime.utcnow()}
        )
        
        await self.session.commit()
        
        return {"order_id": str(order_id), "status": "paid", "method": "safe"}

    async def get_payment_history(self, order_id: UUID) -> list[dict]:
        """Получить историю платежей по заказу.
        
        Args:
            order_id: UUID заказа
            
        Returns:
            list[dict]: Список записей истории
        """
        result = await self.session.execute(
            text("""
                SELECT status, created_at 
                FROM order_status_history 
                WHERE order_id = :order_id
                ORDER BY created_at
            """),
            {"order_id": order_id}
        )
        rows = result.fetchall()
        return [
            {"status": row[0], "created_at": row[1]} 
            for row in rows
        ]