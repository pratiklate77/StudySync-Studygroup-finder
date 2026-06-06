from __future__ import annotations
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import aiofiles
import magic
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.events.kafka_producer import publish_tutor_application_submitted
from app.kafka.producer import ResilientKafkaProducer
from app.models.user import User
from app.schemas.tutor import TutorBecome, TutorProfileRead, TutorProfileUpdate, TutorStatsRead
from app.services.top_tutors_cache import TopTutorsCacheService
from app.services.tutor_service import TutorService

router = APIRouter()


def get_tutor_service(db: AsyncSession = Depends(get_db)) -> TutorService:
    return TutorService(db)


def get_cache(request: Request, settings: Settings = Depends(get_settings)) -> TopTutorsCacheService:
    return TopTutorsCacheService(getattr(request.app.state, "redis", None), settings)


def get_kafka_producer(request: Request) -> ResilientKafkaProducer:
    return request.app.state.kafka_publisher


VERIFICATION_DOC_ROOT = Path("/app/verification-documents")
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "application/pdf"}


async def validate_and_save_file(file: UploadFile, user_id: UUID, doc_type: str) -> str:
    header = await file.read(2048)
    mime_type = magic.from_buffer(header, mime=True)
    await file.seek(0)

    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type for {file.filename}. Allowed: {ALLOWED_MIME_TYPES}",
        )

    base_dir = Path("/app/verification-documents")
    target_dir = base_dir / str(user_id) / doc_type.lower()
    target_dir.mkdir(parents=True, exist_ok=True)

    extension = Path(file.filename).suffix
    safe_filename = f"{uuid4()}{extension}"
    save_path = target_dir / safe_filename

    file_size = 0
    async with aiofiles.open(save_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):
            file_size += len(chunk)
            if file_size > MAX_FILE_SIZE:
                await buffer.close()
                save_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File {file.filename} exceeds 5MB limit",
                )
            await buffer.write(chunk)

    return str(save_path.relative_to(base_dir))


@router.post("/apply", status_code=status.HTTP_202_ACCEPTED)
async def apply_tutor(
    bio: str = Form(...),
    subjects: str = Form(...),
    hourly_rate: float = Form(...),
    identity_proof: UploadFile = File(...),
    highest_degree: UploadFile = File(...),
    extra_certificates: list[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    service: TutorService = Depends(get_tutor_service),
    producer: ResilientKafkaProducer = Depends(get_kafka_producer),
    settings: Settings = Depends(get_settings),
):
    if current_user.role and current_user.role.lower() == "tutor":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "User is already a verified tutor.")
        
    if not bio.strip() or not subjects.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bio and subjects cannot be empty.")
    
    existing = await service.get_tutor_by_user_id_safe(current_user.id)
    if existing and not existing.is_verified:
        raise HTTPException(status.HTTP_409_CONFLICT, "A pending application already exists.")
        
    # Create the pending profile
    expertise = [s.strip() for s in subjects.split(",") if s.strip()]
    payload = TutorBecome(bio=bio, expertise=expertise, hourly_rate=Decimal(str(hourly_rate)))
    profile = await service.create_pending_tutor_profile(current_user.id, payload)
    
    # Save files
    docs = []
    try:
        id_path = await validate_and_save_file(identity_proof, current_user.id, "IDENTITY_PROOF")
        docs.append({"document_type": "IDENTITY_PROOF", "file_name": identity_proof.filename, "file_url": id_path})
        
        deg_path = await validate_and_save_file(highest_degree, current_user.id, "HIGHEST_DEGREE")
        docs.append({"document_type": "HIGHEST_DEGREE", "file_name": highest_degree.filename, "file_url": deg_path})
        
        if extra_certificates:
            for cert in extra_certificates:
                if cert.size == 0 or not cert.filename: continue
                cert_path = await validate_and_save_file(cert, current_user.id, "CERTIFICATE")
                docs.append({"document_type": "CERTIFICATE", "file_name": cert.filename, "file_url": cert_path})
            
    except Exception as e:
        # cleanup omitted for brevity, but let's re-raise
        raise e

    # Publish Kafka event with all application details
    await publish_tutor_application_submitted(
        producer,
        settings,
        user_id=current_user.id,
        bio=bio,
        subjects=expertise,
        hourly_rate=str(hourly_rate),
        documents=docs,
    )

    return {
        "success": True,
        "message": "Tutor application submitted successfully",
        "verification_status": "PENDING"
    }


@router.post("/become", response_model=TutorProfileRead, status_code=201)
async def become_tutor(
    payload: TutorBecome,
    current_user: User = Depends(get_current_user),
    service: TutorService = Depends(get_tutor_service),
) -> TutorProfileRead:
    profile = await service.become_tutor(current_user, payload)
    return TutorProfileRead.model_validate(profile, from_attributes=True)


@router.get("/leaderboard", response_model=list[TutorProfileRead])
async def top_tutors_leaderboard(
    service: TutorService = Depends(get_tutor_service),
    cache: TopTutorsCacheService = Depends(get_cache),
    settings: Settings = Depends(get_settings),
    limit: int = Query(20, ge=1, le=50),
) -> list[TutorProfileRead]:
    return await service.leaderboard(settings=settings, cache=cache, limit=limit)


@router.get("/search", response_model=list[TutorProfileRead])
async def search_tutors(
    expertise: list[str] | None = Query(None),
    min_rating: float | None = Query(None, ge=0, le=5),
    verified_only: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: User = Depends(get_current_user),
    service: TutorService = Depends(get_tutor_service),
) -> list[TutorProfileRead]:
    return await service.search_tutors(
        expertise_tags=expertise,
        min_rating=min_rating,
        verified_only=verified_only,
        limit=limit,
        offset=offset,
    )


@router.patch("/profile", response_model=TutorProfileRead)
async def update_tutor_profile(
    payload: TutorProfileUpdate,
    current_user: User = Depends(get_current_user),
    service: TutorService = Depends(get_tutor_service),
) -> TutorProfileRead:
    profile = await service.get_tutor_by_user_id(current_user.id)
    return await service.update_tutor_profile(profile.id, current_user.id, payload)


@router.delete("/profile", response_model=TutorProfileRead)
async def delete_tutor_profile(
    current_user: User = Depends(get_current_user),
    service: TutorService = Depends(get_tutor_service),
) -> TutorProfileRead:
    profile = await service.get_tutor_by_user_id(current_user.id)
    return await service.delete_tutor_profile(profile.id, current_user.id)


@router.get("/{tutor_id}/stats", response_model=TutorStatsRead)
async def get_tutor_stats(
    tutor_id: UUID,
    _: User = Depends(get_current_user),
    service: TutorService = Depends(get_tutor_service),
) -> TutorStatsRead:
    return await service.get_tutor_stats(tutor_id)


@router.get("/by-user/{user_id}", response_model=TutorProfileRead)
async def get_tutor_by_user(
    user_id: UUID,
    service: TutorService = Depends(get_tutor_service),
) -> TutorProfileRead:
    return await service.get_tutor_by_user_id(user_id)


@router.get("/{tutor_id}", response_model=TutorProfileRead)
async def get_tutor(
    tutor_id: UUID,
    service: TutorService = Depends(get_tutor_service),
) -> TutorProfileRead:
    return await service.get_tutor_by_id(tutor_id)

