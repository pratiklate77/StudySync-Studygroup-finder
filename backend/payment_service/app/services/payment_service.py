from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import uuid
from datetime import datetime
from typing import List

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.database import DatabaseManager
from app.models.payment import Payment, PaymentStatus
from app.models.wallet import Transaction, TransactionType, Wallet
from app.schemas.payment import (
    PaymentConfirmRequest,
    PaymentIntentRequest,
    PaymentIntentResponse,
    PaymentResponse,
    RefundRequest,
    TransactionResponse,
    WalletActionRequest,
    WalletBalanceResponse,
    WalletTransactionsResponse,
)


class PaymentService:
    def __init__(
        self,
        db_manager: DatabaseManager,
        redis: Redis,
        settings: Settings,
        kafka_producer=None,
    ) -> None:
        self.db_manager = db_manager
        self.redis = redis
        self.settings = settings
        self.kafka_producer = kafka_producer

    async def create_payment_intent(
        self,
        payload: PaymentIntentRequest,
    ) -> PaymentIntentResponse:
        platform_fee = self._calculate_platform_fee(payload.amount)
        payment = Payment(
            user_id=payload.user_id,
            tutor_id=payload.tutor_id,
            session_id=payload.session_id,
            amount=payload.amount,
            platform_fee=platform_fee,
            status=PaymentStatus.PENDING,
            payment_method=payload.payment_method,
        )

        async with self.db_manager.SessionLocal() as session:
            session.add(payment)
            await session.commit()
            await session.refresh(payment)

        return PaymentIntentResponse(
            payment_id=payment.id,
            status=payment.status,
            amount=payment.amount,
            platform_fee=payment.platform_fee,
            payment_method=payment.payment_method,
            created_at=payment.created_at.isoformat(),
        )

    async def confirm_payment(
        self,
        payload: PaymentConfirmRequest,
    ) -> PaymentResponse | None:
        async with self.db_manager.SessionLocal() as session:
            payment = await self._get_payment_by_id(payload.payment_id, session)
            if not payment or payment.status != PaymentStatus.PENDING:
                return None

            payment.status = PaymentStatus.COMPLETED
            payment.provider_id = payload.provider_id
            payment.updated_at = datetime.utcnow()

            if payment.payment_method.lower() == "wallet":
                payer_wallet = await self._get_or_create_wallet(payment.user_id, session)
                if payer_wallet.balance < payment.amount:
                    return None
                payer_wallet.balance -= payment.amount
                await self._create_transaction(
                    session=session,
                    wallet=payer_wallet,
                    payment_id=payment.id,
                    transaction_type=TransactionType.DEBIT,
                    amount=payment.amount,
                    description="Payment completed from wallet",
                )

            tutor_wallet = await self._get_or_create_wallet(payment.tutor_id, session)
            net_amount = payment.amount - payment.platform_fee
            tutor_wallet.balance += net_amount
            await self._create_transaction(
                session=session,
                wallet=tutor_wallet,
                payment_id=payment.id,
                transaction_type=TransactionType.CREDIT,
                amount=net_amount,
                description="Tutor payout after payment completion",
            )

            await session.commit()
            await session.refresh(payment)

        await self._invalidate_wallet_cache(payment.user_id)
        await self._invalidate_wallet_cache(payment.tutor_id)

        # Publish PAYMENT_SUCCESS so session_service can add participant
        await self._publish_payment_event("PAYMENT_SUCCESS", payment)

        return self._build_payment_response(payment)

    async def refund_payment(
        self,
        payment_id: uuid.UUID,
        payload: RefundRequest,
    ) -> PaymentResponse | None:
        async with self.db_manager.SessionLocal() as session:
            payment = await self._get_payment_by_id(payment_id, session)
            if not payment or payment.status != PaymentStatus.COMPLETED:
                return None

            payment.status = PaymentStatus.REFUNDED
            payment.updated_at = datetime.utcnow()

            if payment.payment_method.lower() == "wallet":
                payer_wallet = await self._get_or_create_wallet(payment.user_id, session)
                payer_wallet.balance += payment.amount
                await self._create_transaction(
                    session=session,
                    wallet=payer_wallet,
                    payment_id=payment.id,
                    transaction_type=TransactionType.REFUND,
                    amount=payment.amount,
                    description=payload.reason or "Wallet refund",
                )

            tutor_wallet = await self._get_or_create_wallet(payment.tutor_id, session)
            net_amount = payment.amount - payment.platform_fee
            if tutor_wallet.balance >= net_amount:
                tutor_wallet.balance -= net_amount
                await self._create_transaction(
                    session=session,
                    wallet=tutor_wallet,
                    payment_id=payment.id,
                    transaction_type=TransactionType.DEBIT,
                    amount=net_amount,
                    description="Payout reversal after refund",
                )

            await session.commit()
            await session.refresh(payment)

        await self._invalidate_wallet_cache(payment.user_id)
        await self._invalidate_wallet_cache(payment.tutor_id)

        return self._build_payment_response(payment)

    async def get_payment(self, payment_id: uuid.UUID) -> PaymentResponse | None:
        async with self.db_manager.SessionLocal() as session:
            payment = await self._get_payment_by_id(payment_id, session)
            if not payment:
                return None
            return self._build_payment_response(payment)

    async def get_wallet_balance(self, user_id: uuid.UUID) -> WalletBalanceResponse:
        cached = await self.redis.get(self._wallet_cache_key(user_id))
        if cached:
            return WalletBalanceResponse(user_id=user_id, balance=Decimal(cached.decode()))

        async with self.db_manager.SessionLocal() as session:
            wallet = await self._get_or_create_wallet(user_id, session)
            response = WalletBalanceResponse(user_id=user_id, balance=wallet.balance)

        await self.redis.setex(
            self._wallet_cache_key(user_id),
            self.settings.cache_ttl_seconds,
            str(wallet.balance),
        )
        return response

    async def get_wallet_transactions(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        per_page: int = 20,
    ) -> WalletTransactionsResponse:
        async with self.db_manager.SessionLocal() as session:
            wallet = await self._get_or_create_wallet(user_id, session)
            offset = (page - 1) * per_page
            result = await session.execute(
                select(Transaction)
                .where(Transaction.wallet_id == wallet.id)
                .order_by(Transaction.created_at.desc())
                .offset(offset)
                .limit(per_page)
            )
            transactions = result.scalars().all()

        return WalletTransactionsResponse(
            user_id=user_id,
            balance=wallet.balance,
            transactions=[self._build_transaction_response(tx) for tx in transactions],
        )

    async def add_wallet_money(self, payload: WalletActionRequest) -> WalletBalanceResponse:
        async with self.db_manager.SessionLocal() as session:
            wallet = await self._get_or_create_wallet(payload.user_id, session)
            wallet.balance += payload.amount
            await self._create_transaction(
                session=session,
                wallet=wallet,
                payment_id=None,
                transaction_type=TransactionType.CREDIT,
                amount=payload.amount,
                description=payload.description or "Wallet top-up",
            )
            await session.commit()
            await session.refresh(wallet)

        await self._invalidate_wallet_cache(payload.user_id)
        return WalletBalanceResponse(user_id=payload.user_id, balance=wallet.balance)

    async def withdraw_wallet_money(self, payload: WalletActionRequest) -> WalletBalanceResponse | None:
        async with self.db_manager.SessionLocal() as session:
            wallet = await self._get_or_create_wallet(payload.user_id, session)
            if wallet.balance < payload.amount:
                return None
            wallet.balance -= payload.amount
            await self._create_transaction(
                session=session,
                wallet=wallet,
                payment_id=None,
                transaction_type=TransactionType.DEBIT,
                amount=payload.amount,
                description=payload.description or "Wallet withdrawal",
            )
            await session.commit()
            await session.refresh(wallet)

        await self._invalidate_wallet_cache(payload.user_id)
        return WalletBalanceResponse(user_id=payload.user_id, balance=wallet.balance)

    async def get_admin_earnings(self) -> dict:
        """Total platform commission from all completed payments."""
        from sqlalchemy import text
        async with self.db_manager.SessionLocal() as session:
            result = await session.execute(
                text("SELECT COALESCE(SUM(platform_fee), 0), COUNT(*) FROM payments WHERE status = 'completed'")
            )
            row = result.one()
            total_commission = float(row[0])
            total_payments = int(row[1])

            recent = await session.execute(
                text(
                    "SELECT id, session_id, amount, platform_fee, created_at "
                    "FROM payments WHERE status = 'completed' "
                    "ORDER BY created_at DESC LIMIT 20"
                )
            )
            transactions = [
                {
                    "payment_id": str(r.id),
                    "session_id": str(r.session_id),
                    "amount": float(r.amount),
                    "commission": float(r.platform_fee),
                    "created_at": r.created_at.isoformat(),
                }
                for r in recent.fetchall()
            ]
        return {
            "total_commission": total_commission,
            "total_payments": total_payments,
            "commission_rate": self.settings.platform_fee_percentage,
            "transactions": transactions,
        }

    async def get_tutor_earnings(self, tutor_id: uuid.UUID) -> dict:
        """Total net earnings for a specific tutor from completed payments."""
        from sqlalchemy import text
        async with self.db_manager.SessionLocal() as session:
            result = await session.execute(
                text(
                    "SELECT COALESCE(SUM(amount - platform_fee), 0), COUNT(*) "
                    "FROM payments WHERE status = 'completed' AND tutor_id = :tutor_id"
                ),
                {"tutor_id": tutor_id},
            )
            row = result.one()
            total_earnings = float(row[0])
            total_payments = int(row[1])

            recent = await session.execute(
                text(
                    "SELECT id, session_id, amount, platform_fee, created_at "
                    "FROM payments WHERE status = 'completed' AND tutor_id = :tutor_id "
                    "ORDER BY created_at DESC LIMIT 20"
                ),
                {"tutor_id": tutor_id},
            )
            transactions = [
                {
                    "payment_id": str(r.id),
                    "session_id": str(r.session_id),
                    "gross": float(r.amount),
                    "net": float(r.amount - r.platform_fee),
                    "platform_fee": float(r.platform_fee),
                    "created_at": r.created_at.isoformat(),
                }
                for r in recent.fetchall()
            ]
        return {
            "total_earnings": total_earnings,
            "total_payments": total_payments,
            "transactions": transactions,
        }

    async def _get_payment_by_id(self, payment_id: uuid.UUID, session: AsyncSession) -> Payment | None:
        result = await session.execute(select(Payment).where(Payment.id == payment_id))
        return result.scalar_one_or_none()

    async def _get_or_create_wallet(self, user_id: uuid.UUID, session: AsyncSession) -> Wallet:
        result = await session.execute(select(Wallet).where(Wallet.user_id == user_id))
        wallet = result.scalar_one_or_none()
        if wallet:
            return wallet

        wallet = Wallet(user_id=user_id, balance=Decimal("0.00"))
        session.add(wallet)
        await session.flush()
        return wallet

    async def _create_transaction(
        self,
        session: AsyncSession,
        wallet: Wallet,
        payment_id: uuid.UUID | None,
        transaction_type: str,
        amount: Decimal,
        description: str | None = None,
    ) -> Transaction:
        transaction = Transaction(
            wallet_id=wallet.id,
            payment_id=payment_id,
            type=transaction_type,
            amount=amount,
            description=description,
        )
        session.add(transaction)
        return transaction

    async def _invalidate_wallet_cache(self, user_id: uuid.UUID) -> None:
        await self.redis.delete(self._wallet_cache_key(user_id))

    def _wallet_cache_key(self, user_id: uuid.UUID) -> str:
        return f"payment:wallet:{user_id}:balance"

    def _calculate_platform_fee(self, amount: Decimal) -> Decimal:
        fee = amount * Decimal(str(self.settings.platform_fee_percentage)) / Decimal("100")
        return fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _build_payment_response(self, payment: Payment) -> PaymentResponse:
        return PaymentResponse(
            payment_id=payment.id,
            user_id=payment.user_id,
            tutor_id=payment.tutor_id,
            session_id=payment.session_id,
            amount=payment.amount,
            platform_fee=payment.platform_fee,
            status=payment.status,
            payment_method=payment.payment_method,
            provider_id=payment.provider_id,
            created_at=payment.created_at.isoformat(),
            updated_at=payment.updated_at.isoformat(),
        )

    def _build_transaction_response(self, transaction: Transaction) -> TransactionResponse:
        return TransactionResponse(
            transaction_id=transaction.id,
            wallet_id=transaction.wallet_id,
            payment_id=transaction.payment_id,
            type=transaction.type,
            amount=transaction.amount,
            description=transaction.description,
            created_at=transaction.created_at.isoformat(),
        )

    async def _publish_payment_event(self, event_type: str, payment: Payment) -> None:
        """Publish payment event to Kafka if producer is available."""
        if not self.kafka_producer:
            return
        import json
        from datetime import datetime, timezone
        event = {
            "event_type": event_type,
            "payment_id": str(payment.id),
            "user_id": str(payment.user_id),
            "tutor_id": str(payment.tutor_id),
            "session_id": str(payment.session_id),
            "amount": str(payment.amount),
            "student_id": str(payment.user_id),  # alias for session_service consumer
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await self.kafka_producer.send_and_wait(
                self.settings.kafka_payment_events_topic,
                json.dumps(event).encode(),
                key=str(payment.session_id).encode(),
            )
        except Exception:
            pass  # non-critical — payment already committed
