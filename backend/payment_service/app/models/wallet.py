from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, DECIMAL, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class TransactionType(str):
    CREDIT = "credit"
    DEBIT = "debit"
    PAYMENT = "payment"
    REFUND = "refund"


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), unique=True, nullable=False)
    balance = Column(DECIMAL(10, 2), default=0.00, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    transactions = relationship("Transaction", back_populates="wallet")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False)
    payment_id = Column(UUID(as_uuid=True), nullable=True)
    type = Column(String(length=20), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    description = Column(String(length=512), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    wallet = relationship("Wallet", back_populates="transactions")
