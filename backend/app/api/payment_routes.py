"""API endpoints для тестирования конкурентных оплат."""
import uuid
import asyncio
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db import get_db, SessionLocal
from app.application.payment_service import PaymentService

router = APIRouter(prefix="/api/payments", tags=["payments"])


class PaymentRequest(BaseModel):
    order_id: uuid.UUID
    mode: Literal["safe", "unsafe"] = "safe"


class PaymentResponse(BaseModel):
    success: bool
    message: str
    order_id: uuid.UUID
    status: str | None = None


class PaymentHistoryResponse(BaseModel):
    order_id: uuid.UUID
    payment_count: int
    payments: list[dict]


@router.post("/pay", response_model=PaymentResponse)
async def pay_order(request: PaymentRequest, session: AsyncSession = Depends(get_db)):
    """Оплатить заказ."""
    try:
        service = PaymentService(session)
        if request.mode == "safe":
            result = await service.pay_order_safe(request.order_id)
        else:
            result = await service.pay_order_unsafe(request.order_id)
        return PaymentResponse(
            success=True,
            message=f"Order paid successfully ({request.mode})",
            order_id=request.order_id,
            status=result.get("status", "paid")
        )
    except Exception as e:
        return PaymentResponse(success=False, message=str(e), order_id=request.order_id)


@router.get("/history/{order_id}", response_model=PaymentHistoryResponse)
async def get_payment_history(order_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    """История оплат заказа."""
    try:
        service = PaymentService(session)
        history = await service.get_payment_history(order_id)
        return PaymentHistoryResponse(order_id=order_id, payment_count=len(history), payments=history)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-concurrent")
async def test_concurrent_payment(request: PaymentRequest, session: AsyncSession = Depends(get_db)):
    """Демонстрация race condition - запускает две параллельные оплаты.

    Использует Barrier для синхронизации - обе транзакции начинают SELECT одновременно!
    """
    # Barrier синхронизирует старт обеих транзакций
    start_barrier = asyncio.Barrier(2)

    async def attempt_1():
        async with SessionLocal() as s1:
            try:
                svc = PaymentService(s1)
                # Передаём barrier в сервис
                if request.mode == "safe":
                    result = await svc.pay_order_safe(request.order_id, start_barrier)
                else:
                    result = await svc.pay_order_unsafe(request.order_id, start_barrier)
                return {"success": True, "result": result, "attempt": 1}
            except Exception as e:
                return {"success": False, "error": str(e), "attempt": 1}

    async def attempt_2():
        async with SessionLocal() as s2:
            try:
                svc = PaymentService(s2)
                if request.mode == "safe":
                    result = await svc.pay_order_safe(request.order_id, start_barrier)
                else:
                    result = await svc.pay_order_unsafe(request.order_id, start_barrier)
                return {"success": True, "result": result, "attempt": 2}
            except Exception as e:
                return {"success": False, "error": str(e), "attempt": 2}

    results = await asyncio.gather(attempt_1(), attempt_2(), return_exceptions=True)

    service = PaymentService(session)
    history = await service.get_payment_history(request.order_id)

    success_count = sum(1 for r in results if isinstance(r, dict) and r.get("success"))

    return {
        "mode": request.mode,
        "order_id": str(request.order_id),
        "results": results,
        "summary": {
            "total_attempts": 2,
            "successful": success_count,
            "failed": 2 - success_count,
            "payment_count_in_history": len(history),
            "race_condition_detected": len(history) > 1
        },
        "history": history,
        "message": f"{'⚠️ RACE CONDITION!' if len(history) > 1 else '✅ No race condition'} Order paid {len(history)} time(s)"
    }
