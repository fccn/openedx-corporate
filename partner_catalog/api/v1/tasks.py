"""Celery tasks for partner catalog bulk operations."""

from __future__ import annotations

import csv
from io import StringIO
from typing import Any, Dict, List

from celery import shared_task
from django.contrib.auth import get_user_model

from partner_catalog.models import CatalogLearner


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

        obj, created_flag = CatalogLearner.objects.get_or_create(
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
