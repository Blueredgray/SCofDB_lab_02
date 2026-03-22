"""Сервис оплаты с демонстрацией race condition."""
import uuid
import asyncio
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
        Имитация реальной задержки между проверкой и оплатой.
        """
        async with self.session.begin():
            # READ COMMITTED (по умолчанию) - видит только закоммиченные данные
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

            # ⚠️ Имитация задержки (проверка баланса, связывание с платёжной системой...)
            # Это создаёт "окно" для race condition!
            await asyncio.sleep(0.2)  # 200ms

            # Триггер log_status_change автоматически добавит запись в историю
            await self.session.execute(
                text("UPDATE orders SET status = 'paid' WHERE id = :order_id"),
                {"order_id": order_id}
            )

        return {
            "order_id": str(order_id),
            "status": "paid",
            "message": "Order paid successfully (unsafe)"
        }

    async def pay_order_safe(self, order_id: uuid.UUID) -> dict:
        """Безопасная оплата - REPEATABLE READ + FOR UPDATE.

        FOR UPDATE блокирует строку, второй транзакции придётся ждать.
        После коммита первой, вторая увидит изменённый статус.
        """
        async with self.session.begin():
            # REPEATABLE READ - транзакция видит снапшот данных на момент начала
            await self.session.execute(
                text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            )

            # FOR UPDATE блокирует строку до конца транзакции
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

            # Имитация задержки - но строка уже заблокирована FOR UPDATE!
            await asyncio.sleep(0.2)  # 200ms

            # Триггер log_status_change автоматически добавит запись в историю
            await self.session.execute(
                text("UPDATE orders SET status = 'paid' WHERE id = :order_id"),
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
                "changed_at": str(row[3])
            })

        return history
