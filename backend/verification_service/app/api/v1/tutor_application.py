"""
DEPRECATED: This endpoint has been replaced.

Tutor applications are now submitted via the Identity Service:
    POST /api/v1/tutors/apply  (identity_service)

The Identity Service publishes a TUTOR_APPLICATION_SUBMITTED event on the
VERIFICATION_EVENTS topic. The VerificationEventsConsumer in this service
consumes that event and creates the TutorVerificationRequest + documents
in the verification database automatically.

This file is kept as reference only and is no longer registered in the API router.
"""

from __future__ import annotations

import os
import uuid
import magic
import aiofiles
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.enums import DocumentType, VerificationStatus
from app.models.tutor_verification_request import TutorVerificationRequest
from app.models.verification_document import VerificationDocument
from app.models.user import User

router = APIRouter()

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "application/pdf"}

async def validate_and_save_file(file: UploadFile, user_id: uuid.UUID, doc_type: str) -> str:
    # Validate MIME type using python-magic
    header = await file.read(2048)
    mime_type = magic.from_buffer(header, mime=True)
    await file.seek(0)
    
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type for {file.filename}. Allowed: {ALLOWED_MIME_TYPES}"
        )
    
    base_dir = Path(os.getenv("VERIFICATION_DOC_ROOT", "/app/verification-documents"))
    target_dir = base_dir / str(user_id) / doc_type.lower()
    target_dir.mkdir(parents=True, exist_ok=True)
    
    extension = Path(file.filename).suffix
    safe_filename = f"{uuid.uuid4()}{extension}"
    save_path = target_dir / safe_filename
    
    file_size = 0
    async with aiofiles.open(save_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            file_size += len(chunk)
            if file_size > MAX_FILE_SIZE:
                await buffer.close()
                save_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File {file.filename} exceeds {MAX_FILE_SIZE // (1024*1024)}MB limit"
                )
            await buffer.write(chunk)
            
    # Return relative path for DB
    return str(save_path.relative_to(base_dir))

@router.post(
    "/tutor-application",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a tutor onboarding application",
)
async def submit_tutor_application(
    request: Request,
    bio: str = Form(...),
    subjects: str = Form(...),
    experience_years: int = Form(...),
    hourly_rate: float = Form(...),
    identity_proof: UploadFile = File(...),
    highest_degree: UploadFile = File(...),
    extra_certificates: List[UploadFile] = File(default=[]),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role and user.role.lower() == "tutor":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a verified tutor."
        )
        
    if not bio or not bio.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bio cannot be empty."
        )
        
    if not subjects or not subjects.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subjects cannot be empty."
        )

    # 1. Check for duplicate pending requests
    existing = await db.execute(
        select(TutorVerificationRequest).where(
            TutorVerificationRequest.user_id == user.id,
            TutorVerificationRequest.status.in_([VerificationStatus.PENDING, VerificationStatus.UNDER_REVIEW])
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A pending tutor application already exists for this user."
        )

    # 2. Persist the request row
    verification_request = TutorVerificationRequest(
        user_id=user.id,
        bio=bio,
        subjects=subjects,
        experience_years=experience_years,
        hourly_rate=hourly_rate,
        status=VerificationStatus.PENDING,
    )
    db.add(verification_request)
    await db.flush()  # Get request ID

    docs_to_add = []
    
    try:
        # 3. Process required documents
        id_path = await validate_and_save_file(identity_proof, user.id, DocumentType.IDENTITY_PROOF.value)
        docs_to_add.append(
            VerificationDocument(
                request_id=verification_request.id,
                file_name=identity_proof.filename,
                file_url=id_path,
                document_type=DocumentType.IDENTITY_PROOF.value,
            )
        )
        
        degree_path = await validate_and_save_file(highest_degree, user.id, DocumentType.HIGHEST_DEGREE.value)
        docs_to_add.append(
            VerificationDocument(
                request_id=verification_request.id,
                file_name=highest_degree.filename,
                file_url=degree_path,
                document_type=DocumentType.HIGHEST_DEGREE.value,
            )
        )
        
        # 4. Process optional certificates
        for cert in extra_certificates:
            if cert.size == 0 or not cert.filename:
                continue
            cert_path = await validate_and_save_file(cert, user.id, DocumentType.CERTIFICATE.value)
            docs_to_add.append(
                VerificationDocument(
                    request_id=verification_request.id,
                    file_name=cert.filename,
                    file_url=cert_path,
                    document_type=DocumentType.CERTIFICATE.value,
                )
            )
            
        db.add_all(docs_to_add)
        await db.commit()
        
    except Exception as e:
        await db.rollback()
        raise e

    # 5. Publish Kafka Event
    producer = request.app.state.kafka_producer
    await producer.publish_tutor_application_submitted(
        request_id=str(verification_request.id),
        user_id=str(user.id),
    )

    return {
        "success": True,
        "message": "Tutor application submitted successfully",
        "verification_status": verification_request.status.value
    }
