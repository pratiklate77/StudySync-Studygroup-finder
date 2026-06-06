from __future__ import annotations

import enum

class DocumentType(str, enum.Enum):
    IDENTITY_PROOF = "IDENTITY_PROOF"
    HIGHEST_DEGREE = "HIGHEST_DEGREE"
    CERTIFICATE = "CERTIFICATE"

class VerificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"
