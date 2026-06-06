from __future__ import annotations

from typing import Any


# Default templates for all consumed events
TEMPLATES: dict[str, dict[str, str]] = {
    "USER_REGISTERED": {
        "title": "Welcome to StudySync!",
        "body": "Your account has been created. Start exploring tutors and sessions.",
    },
    "SESSION_CREATED": {
        "title": "New Session Available",
        "body": "A new tutoring session '{title}' has been created.",
    },
    "SESSION_CANCELLED": {
        "title": "Session Cancelled",
        "body": "The session '{title}' has been cancelled.",
    },
    "SESSION_REMINDER": {
        "title": "Session Reminder",
        "body": "Your session '{title}' starts in 30 minutes.",
    },
    "GROUP_JOINED": {
        "title": "New Member Joined",
        "body": "Someone joined your study group '{group_name}'.",
    },
    "GROUP_CREATED": {
        "title": "Study Group Created",
        "body": "Your study group '{group_name}' has been created successfully.",
    },
    "CHAT_MESSAGE_SENT": {
        "title": "New Message",
        "body": "You have a new message in '{group_name}'.",
    },
    "PAYMENT_SUCCESS": {
        "title": "Payment Successful",
        "body": "Your payment of ${amount} was processed successfully.",
    },
    "PAYMENT_FAILED": {
        "title": "Payment Failed",
        "body": "Your payment of ${amount} could not be processed. Please try again.",
    },
    "TUTOR_VERIFIED": {
        "title": "Verification Approved",
        "body": "Congratulations! Your tutor profile has been verified.",
    },
    "TUTOR_REJECTED": {
        "title": "Verification Rejected",
        "body": "Your verification request was rejected. Reason: {reason}",
    },
    "TUTOR_RECOMMENDED": {
        "title": "You've Been Recommended!",
        "body": "You appeared in {count} student recommendations today.",
    },
    "VERIFICATION_SUBMITTED": {
        "title": "Verification Request Received",
        "body": "Your {request_type} verification request has been submitted and is under review.",
    },
    "VERIFICATION_APPROVED": {
        "title": "Verification Approved",
        "body": "Your {request_type} verification has been approved.",
    },
    "VERIFICATION_REJECTED": {
        "title": "Verification Rejected",
        "body": "Your {request_type} verification was rejected. Reason: {reason}",
    },
    "SESSION_RATED": {
        "title": "New Session Rating Received",
        "body": "A student rated your completed session with {rating} stars.",
    },
    "RATING_SUBMITTED": {
        "title": "New Session Rating Received",
        "body": "A student rated your completed session with {rating} stars.",
    },
}


def render_template(event_type: str, context: dict[str, Any]) -> tuple[str, str]:
    """Render title and body from template with context substitution."""
    template = TEMPLATES.get(event_type, {
        "title": "StudySync Notification",
        "body": f"You have a new {event_type.lower().replace('_', ' ')} notification.",
    })
    try:
        title = template["title"].format(**context)
        body = template["body"].format(**context)
    except KeyError:
        title = template["title"]
        body = template["body"]
    return title, body
