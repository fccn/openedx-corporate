"""Celery tasks for corporate partner access bulk operations."""

from __future__ import annotations

import csv
from io import StringIO
from typing import Any, Dict, List, Optional

from celery import shared_task
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from corporate_partner_access.models import CatalogCourseEnrollmentAllowed, CorporatePartnerCatalogLearner


@shared_task(bind=True)
def bulk_upload_learners(_self, csv_content: str, catalog_id: int) -> Dict[str, Any]:
    """
    Celery task to process bulk learner uploads from CSV content.
    CSV columns: username (or email), optional active (defaults to True).
    """
    User = get_user_model()
    created: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []

    reader = csv.DictReader(StringIO(csv_content))
    for row in reader:
        username = row.get("username")
        email = row.get("email")
        active = row.get("active", "True").strip().lower() in ("true", "1", "yes", "y", "t")
        user = None

        if username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                failed.append({"username": username, "error": "User not found"})
                continue
        elif email:
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                failed.append({"email": email, "error": "User not found"})
                continue
        else:
            failed.append({"error": "Missing username/email in row"})
            continue

        obj, created_flag = CorporatePartnerCatalogLearner.objects.get_or_create(
            catalog_id=catalog_id,
            user=user,
            defaults={"active": active},
        )
        if not created_flag:
            obj.active = active
            obj.save()

        created.append({
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "active": obj.active,
        })

    return {"created": created, "failed": failed}


@shared_task(bind=True)
def bulk_upload_invitations(
    _self,
    csv_content: str,
    catalog_course_id: Optional[int] = None,
    invited_by_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Celery task to process bulk invitations uploads from CSV content.
    CSV columns: email
    """
    User = get_user_model()
    created: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []

    reader = csv.DictReader(StringIO(csv_content))

    for row in reader:
        raw_email = (row.get("email") or row.get("invite_email") or "").strip().lower()
        if not raw_email:
            failed.append({"error": "Empty email", "row": row})
            continue
        try:
            validate_email(raw_email)
        except ValidationError:
            failed.append({"email": raw_email, "error": "Invalid email format", "row": row})
            continue

        user = User.objects.filter(email__iexact=raw_email).first()

        try:
            obj, was_created = CatalogCourseEnrollmentAllowed.objects.get_or_create(
                catalog_course_id=catalog_course_id,
                invite_email=raw_email,
                defaults={
                    "user": user,
                    "invited_by_id": invited_by_id,
                    "status": CatalogCourseEnrollmentAllowed.Status.SENT,
                },
            )

            if not was_created and user and obj.user_id is None:
                obj.user_id = user.id
                obj.save(update_fields=["user"])

            created.append({
                "id": obj.id,
                "email": raw_email,
                "catalog_course_id": catalog_course_id,
                "status": obj.status,
                "status_display": obj.get_status_display(),
                "created_now": was_created,
            })
        except Exception as exc:  # pylint: disable=broad-exception-caught
            failed.append({
                "email": raw_email,
                "catalog_course_id": catalog_course_id,
                "error": str(exc),
                "row": row,
            })

    return {"created": created, "failed": failed}
