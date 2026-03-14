"""Payment service with concurrent access control.

Demonstrates race condition problem and solution using isolation levels.
"""
import uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.exceptions import OrderAlreadyPaidError, OrderNotFoundError


class PaymentService:
    """Service for processing payments with different isolation levels."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def pay_order_unsafe(self, order_id: uuid.UUID) -> dict:
        """UNSAFE payment - READ COMMITTED without locks.

        Race condition: two concurrent calls can double-pay!

        Args:
            order_id: Order UUID to pay

        Returns:
            Dict with payment result

        Raises:
            OrderNotFoundError: Order doesn't exist
            OrderAlreadyPaidError: Order already paid (but race condition possible!)
        """
        async with self.session.begin():
            # Read status - no lock, default READ COMMITTED
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

            # Update status
            await self.session.execute(
                text("UPDATE orders SET status = 'paid' WHERE id = :order_id"),
                {"order_id": order_id}
            )

            # Insert history
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
            "message": "Order paid successfully (unsafe method)"
        }

    async def pay_order_safe(self, order_id: uuid.UUID) -> dict:
        """SAFE payment - REPEATABLE READ + FOR UPDATE.

        Prevents race condition with proper locking.

        Args:
            order_id: Order UUID to pay

        Returns:
            Dict with payment result

        Raises:
            OrderNotFoundError: Order doesn't exist
            OrderAlreadyPaidError: Order already paid (blocked by lock)
        """
        async with self.session.begin():
            # Set isolation level
            await self.session.execute(
                text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            )

            # Lock row for update - blocks concurrent access
            result = await self.session.execute(
                text("""
                    SELECT status 
                    FROM orders 
                    WHERE id = :order_id 
                    FOR UPDATE
                """),
                {"order_id": order_id}
            )
            row = result.fetchone()

            if row is None:
                raise OrderNotFoundError(f"Order {order_id} not found")

            status = row[0]

            if status != 'created':
                raise OrderAlreadyPaidError(f"Order {order_id} already paid")

            # Update status
            await self.session.execute(
                text("UPDATE orders SET status = 'paid' WHERE id = :order_id"),
                {"order_id": order_id}
            )

            # Insert history
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
            "message": "Order paid successfully (safe method)"
        }

    async def get_payment_history(self, order_id: uuid.UUID) -> list[dict]:
        """Get payment history for order.

        Used to check how many times order was paid.

        Args:
            order_id: Order UUID

        Returns:
            List of payment records
        """
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
        return [
            {
                "id": str(row[0]),
                "order_id": str(row[1]),
                "status": row[2],
                "changed_at": row[3]
            }
            for row in rows
        ]
