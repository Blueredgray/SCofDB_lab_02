"""Тест демонстрирует race condition при небезопасной оплате.

Тест проходит если произошла двойная оплата (демонстрация проблемы).
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
                "email": f"test_{order_id}@example.com",
                "name": "Test User",
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
async def test_concurrent_payment_unsafe(engine, test_order: UUID):
    """Тест: две параллельные оплаты с небезопасным методом.
    
    Ожидаем: race condition - двойная оплата (две записи в истории).
    """
    order_id = test_order
    
    async def payment_attempt():
        """Одна попытка оплаты с независимой сессией."""
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            service = PaymentService(session)
            try:
                return await service.pay_order_unsafe(order_id)
            except Exception as e:
                return e
    
    # Запускаем две параллельные оплаты
    results = await asyncio.gather(
        payment_attempt(),
        payment_attempt(),
        return_exceptions=True
    )
    
    # Проверяем результаты
    success_count = sum(1 for r in results if isinstance(r, dict))
    error_count = sum(1 for r in results if isinstance(r, Exception))
    
    print(f"\n{'='*60}")
    print("⚠️  RACE CONDITION DETECTED!")
    print(f"{'='*60}")
    print(f"Order {order_id} payment attempts:")
    print(f"  - Successful: {success_count}")
    print(f"  - Failed: {error_count}")
    
    # Проверяем историю в БД
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        service = PaymentService(session)
        history = await service.get_payment_history(order_id)
        
        print(f"\nPayment history records: {len(history)}")
        for i, record in enumerate(history, 1):
            print(f"  {i}. {record['created_at']}: status = {record['status']}")
        
        # Тест проходит если есть двойная оплата (демонстрация проблемы)
        assert len(history) == 2, f"Expected double payment (race condition), got {len(history)} records"
        
        print(f"\n✅ Test PASSED - Race condition demonstrated!")
        print(f"   Order was paid TWICE due to missing FOR UPDATE")