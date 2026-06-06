from __future__ import annotations

from decimal import Decimal
from typing import List
from uuid import UUID

from pydantic import BaseModel, Field


class PaymentIntentRequest(BaseModel):
    user_id: UUID
    tutor_id: UUID
    session_id: UUID
    amount: Decimal = Field(gt=0)
    payment_method: str = Field(min_length=1)


class PaymentIntentResponse(BaseModel):
    payment_id: UUID
    status: str
    amount: Decimal
    platform_fee: Decimal
    payment_method: str
    created_at: str


class PaymentConfirmRequest(BaseModel):
    payment_id: UUID
    provider_id: str | None = None


class RefundRequest(BaseModel):
    reason: str | None = None


class PaymentResponse(BaseModel):
    payment_id: UUID
    user_id: UUID
    tutor_id: UUID
    session_id: UUID
    amount: Decimal
    platform_fee: Decimal
    status: str
    payment_method: str
    provider_id: str | None = None
    created_at: str
    updated_at: str


class WalletBalanceResponse(BaseModel):
    user_id: UUID
    balance: Decimal


class TransactionResponse(BaseModel):
    transaction_id: UUID
    wallet_id: UUID
    payment_id: UUID | None = None
    type: str
    amount: Decimal
    description: str | None = None
    created_at: str


class WalletTransactionsResponse(BaseModel):
    user_id: UUID
    balance: Decimal
    transactions: List[TransactionResponse]


class WalletActionRequest(BaseModel):
    user_id: UUID
    amount: Decimal = Field(gt=0)
    description: str | None = None
