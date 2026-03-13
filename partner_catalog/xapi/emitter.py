"""
Tracking emitters for partner_catalog xAPI events.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from django.db import transaction

try:
    from eventtracking import tracker
except ImportError:  # pragma: no cover
    tracker = None

logger = logging.getLogger(__name__)


def _drop_none(payload: dict[str, Any] | None) -> dict[str, Any]:
    """
    Remove keys with ``None`` values from a payload.
    """
    return {
        key: _json_safe(value)
        for key, value in (payload or {}).items()
        if value is not None
    }


def _json_safe(value: Any) -> Any:
    """
    Ensure event payload values can be serialized by JSON log backends.
    """
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return value


def emit_tracking_event(
    event_name: str,
    *,
    data: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    on_commit: bool = True,
) -> None:
    """
    Emit a tracking event in a best-effort and backward-compatible way.
    """
    cleaned_data = _drop_none(data)
    cleaned_context = _drop_none(context)

    def _emit() -> None:
        if tracker is None:
            logger.debug(
                "Skipping tracking event '%s' because eventtracking is unavailable.",
                event_name,
            )
            return
        emit_fn = tracker.emit
        try:
            if cleaned_context:
                emit_args = (event_name, cleaned_data, cleaned_context)
            else:
                emit_args = (event_name, cleaned_data)
            emit_fn(*emit_args)
        except TypeError:
            # Older event-tracking versions only support emit(name, data).
            emit_fn(event_name, cleaned_data)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Failed to emit tracking event '%s'.", event_name)

    if on_commit:
        transaction.on_commit(_emit)
    else:
        _emit()


def emit_catalog_invitation_tracking_event(
    *,
    event_name: str,
    invitation: Any,
    actor_user_id: int | None = None,
    invitation_channel: str | None = None,
) -> None:
    """
    Emit a partner-catalog invitation tracking event.
    """
    catalog = getattr(invitation, "catalog", None)
    data = {
        "event_name": event_name,
        "invitation_id": getattr(invitation, "id", None),
        "catalog_id": getattr(invitation, "catalog_id", None),
        "partner_id": getattr(catalog, "partner_id", None) if catalog else None,
        "user_id": actor_user_id if actor_user_id is not None else getattr(invitation, "user_id", None),
        "learner_user_id": getattr(invitation, "user_id", None),
        "invited_by_id": getattr(invitation, "invited_by_id", None),
        "removed_by_id": getattr(invitation, "removed_by_id", None),
        "invitation_channel": invitation_channel,
    }
    emit_tracking_event(event_name, data=data, on_commit=True)


def emit_catalog_course_enrollment_tracking_event(
    *,
    event_name: str,
    user_id: int,
    catalog_id: int | None,
    partner_id: int | None,
    course_id: str | None,
    catalog_course_id: int | None,
    enrollment_mode: str | None = None,
    blocked_reason: str | None = None,
    on_commit: bool = True,
) -> None:
    """
    Emit a partner-catalog course enrollment tracking event.
    """
    data = {
        "event_name": event_name,
        "user_id": user_id,
        "catalog_id": catalog_id,
        "partner_id": partner_id,
        "course_id": course_id,
        "catalog_course_id": catalog_course_id,
        "enrollment_mode": enrollment_mode,
        "blocked_reason": blocked_reason,
    }
    emit_tracking_event(event_name, data=data, on_commit=on_commit)
