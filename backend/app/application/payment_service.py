"""Сервис оплаты с демонстрацией race condition."""
import uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.exceptions import OrderAlreadyPaidError, OrderNotFoundError


class PaymentService:
    """Сервис обработки платежей с разными уровнями изоляции."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def pay_order_unsafe(self, order_id: uuid.UUID) -> dict:
        """Небезопасная оплата - READ COMMITTED без блокировок.

        Ломается при конкурентных запросах - двойная оплата!
        """
        async with self.session.begin():
            # Читаем статус без блокировки
            result = await self.session.execute(
                text("SELECT status FROM orders WHERE id = :order_id"),
                {"order_id": order_id}
            )
            row = result.fetchone()

            if row is None:
                raise OrderNotFoundError(f"Order {order_id} not found")

            status = row[0]

            if status != 'created':
                raise OrderAlreadyPaidError(f"Order {order_id} already paid")

            # Обновляем статус
            await self.session.execute(
                text("UPDATE orders SET status = 'paid' WHERE id = :order_id"),
                {"order_id": order_id}
            )

            # Записываем в историю
            await self.session.execute(
                text("""
                    INSERT INTO order_status_history (id, order_id, status, changed_at)
                    VALUES (gen_random_uuid(), :order_id, 'paid', NOW())
                """),
                {"order_id": order_id}
            )

        return {
            "order_id": str(order_id),
            "status": "paid",
            "message": "Order paid successfully (unsafe)"
        }

    async def pay_order_safe(self, order_id: uuid.UUID) -> dict:
        """Безопасная оплата - REPEATABLE READ + FOR UPDATE.

        Корректно работает при конкурентных запросах.
        """
        async with self.session.begin():
            # Устанавливаем уровень изоляции
            await self.session.execute(
                text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            )

            # Блокируем строку для обновления
            result = await self.session.execute(
                text("""
                    SELECT status FROM orders
                    WHERE id = :order_id FOR UPDATE
                """),
                {"order_id": order_id}
            )
            row = result.fetchone()

            if row is None:
                raise OrderNotFoundError(f"Order {order_id} not found")

            status = row[0]

            if status != 'created':
                raise OrderAlreadyPaidError(f"Order {order_id} already paid")

            # Обновляем статус
            await self.session.execute(
                text("UPDATE orders SET status = 'paid' WHERE id = :order_id"),
                {"order_id": order_id}
            )

            # Записываем в историю
            await self.session.execute(
                text("""
                    INSERT INTO order_status_history (id, order_id, status, changed_at)
                    VALUES (gen_random_uuid(), :order_id, 'paid', NOW())
                """),
                {"order_id": order_id}
            )

        return {
            "order_id": str(order_id),
            "status": "paid",
            "message": "Order paid successfully (safe)"
        }

    async def get_payment_history(self, order_id: uuid.UUID) -> list[dict]:
        """Получить историю оплат заказа."""
        result = await self.session.execute(
            text("""
                SELECT id, order_id, status, changed_at
                FROM order_status_history
                WHERE order_id = :order_id AND status = 'paid'
                ORDER BY changed_at
            """),
            {"order_id": order_id}
        )

        rows = result.fetchall()
        history = []

        for row in rows:
            history.append({
                "id": str(row[0]),
                "order_id": str(row[1]),
                "status": row[2],
                "changed_at": row[3]
            })

        return history
