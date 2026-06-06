from __future__ import annotations

from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.schemas.payment import (
    PaymentConfirmRequest,
    PaymentIntentRequest,
    PaymentIntentResponse,
    PaymentResponse,
    RefundRequest,
    WalletActionRequest,
    WalletBalanceResponse,
    WalletTransactionsResponse,
)
from app.services.payment_service import PaymentService

router = APIRouter()


def get_payment_service(request: Request) -> PaymentService:
    return request.app.state.payment_service


@router.post("/payments/create-intent", response_model=PaymentIntentResponse)
async def create_payment_intent(
    request: PaymentIntentRequest,
    payment_service: PaymentService = Depends(get_payment_service),
) -> PaymentIntentResponse:
    return await payment_service.create_payment_intent(request)


@router.post("/payments/confirm", response_model=PaymentResponse)
async def confirm_payment(
    request: PaymentConfirmRequest,
    payment_service: PaymentService = Depends(get_payment_service),
) -> PaymentResponse:
    payment = await payment_service.confirm_payment(request)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment cannot be confirmed or is already finalized",
        )
    return payment


@router.get("/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: UUID,
    payment_service: PaymentService = Depends(get_payment_service),
) -> PaymentResponse:
    payment = await payment_service.get_payment(payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return payment


@router.post("/payments/{payment_id}/refund", response_model=PaymentResponse)
async def refund_payment(
    payment_id: UUID,
    request: RefundRequest,
    payment_service: PaymentService = Depends(get_payment_service),
) -> PaymentResponse:
    payment = await payment_service.refund_payment(payment_id, request)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refund cannot be processed for this payment",
        )
    return payment


@router.get("/wallet/balance", response_model=WalletBalanceResponse)
async def wallet_balance(
    user_id: UUID = Query(..., description="User ID for wallet balance"),
    payment_service: PaymentService = Depends(get_payment_service),
) -> WalletBalanceResponse:
    return await payment_service.get_wallet_balance(user_id)


@router.get("/wallet/transactions", response_model=WalletTransactionsResponse)
async def wallet_transactions(
    user_id: UUID = Query(..., description="User ID for wallet transactions"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    payment_service: PaymentService = Depends(get_payment_service),
) -> WalletTransactionsResponse:
    return await payment_service.get_wallet_transactions(user_id=user_id, page=page, per_page=per_page)


@router.post("/wallet/add-money", response_model=WalletBalanceResponse)
async def add_money(
    request: WalletActionRequest,
    payment_service: PaymentService = Depends(get_payment_service),
) -> WalletBalanceResponse:
    return await payment_service.add_wallet_money(request)


@router.post("/wallet/withdraw", response_model=WalletBalanceResponse)
async def withdraw_money(
    request: WalletActionRequest,
    payment_service: PaymentService = Depends(get_payment_service),
) -> WalletBalanceResponse:
    balance = await payment_service.withdraw_wallet_money(request)
    if not balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient wallet balance",
        )
    return balance


@router.get("/payments/admin/earnings")
async def admin_earnings(
    payment_service: PaymentService = Depends(get_payment_service),
) -> dict:
    return await payment_service.get_admin_earnings()


@router.get("/payments/tutor/{tutor_id}/earnings")
async def tutor_earnings(
    tutor_id: UUID,
    payment_service: PaymentService = Depends(get_payment_service),
) -> dict:
    return await payment_service.get_tutor_earnings(tutor_id)
