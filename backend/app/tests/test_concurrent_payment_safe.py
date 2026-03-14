"""Тест демонстрирует отсутствие race condition при безопасной оплате.

Тест проходит если только одна оплата успешна (демонстрация решения).
"""
from __future__ import annotations

import asyncio
import pytest
from uuid import uuid4, UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.application.payment_service import PaymentService, OrderAlreadyPaidError


# Конфигурация БД для тестов
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/marketplace"


@pytest.fixture
async def engine():
    """Фикстура для создания движка БД."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(engine):
    """Фикстура для сессии БД."""
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest.fixture
async def test_order(engine) -> UUID:
    """Создаёт тестовый заказ для проверки."""
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    order_id = uuid4()
    user_id = uuid4()
    
    async with async_session() as session:
        # Создаём пользователя
        await session.execute(
            text("""
                INSERT INTO users (id, email, name, created_at)
                VALUES (:id, :email, :name, :created_at)
            """),
            {
                "id": user_id,
                "email": f"test_safe_{order_id}@example.com",
                "name": "Test User Safe",
                "created_at": datetime.utcnow()
            }
        )
        
        # Создаём заказ со статусом created
        await session.execute(
            text("""
                INSERT INTO orders (id, user_id, status, total_amount, created_at)
                VALUES (:id, :user_id, 'created', 100.0, :created_at)
            """),
            {
                "id": order_id,
                "user_id": user_id,
                "created_at": datetime.utcnow()
            }
        )
        await session.commit()
    
    yield order_id
    
    # Cleanup
    async with async_session() as session:
        await session.execute(text("DELETE FROM order_status_history WHERE order_id = :id"), {"id": order_id})
        await session.execute(text("DELETE FROM orders WHERE id = :id"), {"id": order_id})
        await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        await session.commit()


@pytest.mark.asyncio
async def test_concurrent_payment_safe(engine, test_order: UUID):
    """Тест: две параллельные оплаты с безопасным методом.
    
    Ожидаем: только одна оплата успешна, вторая получает ошибку.
    """
    order_id = test_order
    
    async def payment_attempt():
        """Одна попытка оплаты с независимой сессией."""
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            service = PaymentService(session)
            try:
                return await service.pay_order_safe(order_id)
            except Exception as e:
                return e
    
    # Запускаем две параллельные оплаты
    results = await asyncio.gather(
        payment_attempt(),
        payment_attempt(),
        return_exceptions=True
    )
    
    # Анализируем результаты
    success_results = [r for r in results if isinstance(r, dict)]
    error_results = [r for r in results if isinstance(r, Exception)]
    
    print(f"\n{'='*60}")
    print("✅ RACE CONDITION PREVENTED!")
    print(f"{'='*60}")
    print(f"Order {order_id} payment attempts:")
    print(f"  - Successful: {len(success_results)}")
    print(f"  - Failed: {len(error_results)}")
    
    if error_results:
        print(f"\nError details: {error_results[0]}")
    
    # Проверяем историю в БД
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        service = PaymentService(session)
        history = await service.get_payment_history(order_id)
        
        print(f"\nPayment history records: {len(history)}")
        for i, record in enumerate(history, 1):
            print(f"  {i}. {record['created_at']}: status = {record['status']}")
        
        # Тест проходит если только одна оплата
        assert len(history) == 1, f"Expected single payment, got {len(history)} records"
        assert len(success_results) == 1, f"Expected 1 success, got {len(success_results)}"
        assert len(error_results) == 1, f"Expected 1 error, got {len(error_results)}"
        assert isinstance(error_results[0], OrderAlreadyPaidError)
        
        print(f"\n✅ Test PASSED - Race condition prevented!")
        print(f"   REPEATABLE READ + FOR UPDATE works correctly")