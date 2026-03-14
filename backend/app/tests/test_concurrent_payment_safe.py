"""Test demonstrating race condition solution.

This test PASSES by confirming that pay_order_safe() prevents double payment.
"""
import asyncio
import pytest
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from app.application.payment_service import PaymentService
from app.domain.exceptions import OrderAlreadyPaidError

# Use same DB as app
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/marketplace"


@pytest.fixture(scope="module")
async def test_engine():
    """Create async engine for tests."""
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20
    )
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    """Create DB session for tests."""
    async with AsyncSession(test_engine) as session:
        yield session


@pytest.fixture
async def test_order(test_engine):
    """Create test order with status 'created'."""
    user_id = uuid.uuid4()
    order_id = uuid.uuid4()

    async with AsyncSession(test_engine) as setup_session:
        async with setup_session.begin():
            # Create user
            await setup_session.execute(
                text("""
                    INSERT INTO users (id, email, name, created_at)
                    VALUES (:user_id, :email, :name, NOW())
                    ON CONFLICT (id) DO NOTHING
                """),
                {
                    "user_id": user_id,
                    "email": f"test_safe_{order_id}@example.com",
                    "name": "Test User Safe"
                }
            )

            # Create order
            await setup_session.execute(
                text("""
                    INSERT INTO orders (id, user_id, status, total_amount, created_at)
                    VALUES (:order_id, :user_id, 'created', 100.00, NOW())
                """),
                {"order_id": order_id, "user_id": user_id}
            )

            # Add history record
            await setup_session.execute(
                text("""
                    INSERT INTO order_status_history (id, order_id, status, changed_at)
                    VALUES (gen_random_uuid(), :order_id, 'created', NOW())
                """),
                {"order_id": order_id}
            )

    yield order_id

    # Cleanup
    async with AsyncSession(test_engine) as cleanup_session:
        async with cleanup_session.begin():
            await cleanup_session.execute(
                text("DELETE FROM order_status_history WHERE order_id = :order_id"),
                {"order_id": order_id}
            )
            await cleanup_session.execute(
                text("DELETE FROM orders WHERE id = :order_id"),
                {"order_id": order_id}
            )
            await cleanup_session.execute(
                text("DELETE FROM users WHERE id = :user_id"),
                {"user_id": user_id}
            )


@pytest.mark.asyncio
async def test_concurrent_payment_safe_prevents_race_condition(
    db_session, test_order, test_engine
):
    """Test shows safe payment prevents race condition.

    Expected: test PASSES confirming single payment only.
    """
    order_id = test_order

    async def payment_attempt_1():
        """First concurrent payment."""
        async with AsyncSession(test_engine) as session1:
            service1 = PaymentService(session1)
            return await service1.pay_order_safe(order_id)

    async def payment_attempt_2():
        """Second concurrent payment."""
        async with AsyncSession(test_engine) as session2:
            service2 = PaymentService(session2)
            return await service2.pay_order_safe(order_id)

    # Run two payments concurrently
    results = await asyncio.gather(
        payment_attempt_1(),
        payment_attempt_2(),
        return_exceptions=True
    )

    # Small delay for DB to settle
    await asyncio.sleep(0.2)

    # Count successes and failures
    success_count = sum(1 for r in results if not isinstance(r, Exception))
    error_count = sum(1 for r in results if isinstance(r, Exception))

    # One should succeed, one should fail
    assert success_count == 1, f"Expected 1 success, got {success_count}"
    assert error_count == 1, f"Expected 1 error, got {error_count}"

    # Check only one payment in history
    async with AsyncSession(test_engine) as check_session:
        service = PaymentService(check_session)
        history = await service.get_payment_history(order_id)

        assert len(history) == 1, (
            f"Expected 1 payment (no race condition!), got {len(history)}"
        )

        print(f"
✅ RACE CONDITION PREVENTED!")
        print(f"Order {order_id} was paid only ONCE:")
        print(f"  - {history[0]['changed_at']}: status = {history[0]['status']}")

        # Show error details
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Attempt {i+1} rejected: {type(result).__name__}: {result}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
