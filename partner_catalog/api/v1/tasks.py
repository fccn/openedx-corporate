"""Celery tasks for partner catalog bulk operations."""

from __future__ import annotations

import csv
from io import StringIO
from typing import Any, Dict, List

from celery import shared_task
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError

from partner_catalog.models import CatalogLearner
from partner_catalog.services.invitations import CatalogLearnerInvitationService
from partner_catalog.xapi.constants import INVITATION_CHANNEL_BULK_CSV

User = get_user_model()


@shared_task(bind=True)
def bulk_upload_invitations(
    _self, csv_content: str, catalog_id: int, invited_by_id: int
) -> Dict[str, Any]:
    """
    Celery task to process bulk invitation uploads from CSV content.
    CSV columns: email
    """
    invitation_service = CatalogLearnerInvitationService()
    success: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []

    try:
        invited_by = User.objects.get(id=invited_by_id)
    except User.DoesNotExist:
        return {"error": f"Invited by user {invited_by_id} not found"}

    reader = csv.DictReader(StringIO(csv_content))
    for row_num, row in enumerate(reader, start=2):
        email = row.get("email", "").strip()

        if not email:
            failed.append({
                "row": row_num,
                "email": "",
                "error": "Missing email in row"
            })
            continue

        try:
            invitation = invitation_service.create_new_invitation(
                invite_email=email,
                catalog_id=catalog_id,
                invited_by=invited_by,
                invitation_channel=INVITATION_CHANNEL_BULK_CSV,
            )
            success.append({
                "row": row_num,
                "email": email,
                "invitation_id": invitation.id,
                "status": invitation.get_status_display()
            })
        except ValidationError as exc:
            failed.append({
                "row": row_num,
                "email": email,
                "error": str(exc.detail[0]) if hasattr(exc, 'detail') else str(exc)
            })

    return {
        "success": success,
        "failed": failed,
        "total": len(success) + len(failed),
        "success_count": len(success),
        "failed_count": len(failed)
    }


@shared_task(bind=True)
def bulk_remove_invitations(
    _self, learner_ids: List[int], removed_by_id: int, catalog_id: str
) -> Dict[str, Any]:
    """
    Celery task to process bulk invitation removals.
    """
    invitation_service = CatalogLearnerInvitationService()
    success = []
    failed = []

    try:
        removed_by = User.objects.get(id=removed_by_id)
    except User.DoesNotExist:
        return {"error": f"Removed by user {removed_by_id} not found"}

    for learner_id in learner_ids:
        try:
            learner = CatalogLearner.objects.get(id=learner_id, catalog_id=catalog_id)

            if not learner.current_invitation:
                failed.append({
                    "learner_id": learner_id,
                    "error": "Invalid learner state: No current invitation to remove"
                })
                continue

            invitation = invitation_service.remove_invitation(
                invitation_id=learner.current_invitation.id,
                user=removed_by
            )
            success.append({
                "learner_id": learner_id,
                "invitation_id": invitation.id,
                "email": invitation.invite_email,
                "status": invitation.get_status_display()
            })
        except CatalogLearner.DoesNotExist:
            failed.append({
                "learner_id": learner_id,
                "error": "Learner not found"
            })
        except ValidationError as exc:
            failed.append({
                "learner_id": learner_id,
                "error": str(exc.detail[0]) if hasattr(exc, 'detail') else str(exc)
            })

    return {
        "success": success,
        "failed": failed,
        "total": len(success) + len(failed),
        "success_count": len(success),
        "failed_count": len(failed)
    }
