"""Celery tasks for corporate partner access bulk operations."""

import csv
from io import StringIO

from django.contrib.auth import get_user_model

try:
    from celery import shared_task
except ImportError:
    # Fallback for test environments without Celery
    def shared_task(bind=False, **kwargs):  # pylint: disable=unused-argument
        def decorator(func):
            return func
        return decorator

from corporate_partner_access.models import CorporatePartnerCatalogLearner


@shared_task(bind=True)
def bulk_upload_learners(self, csv_content, catalog_id):  # pylint: disable=unused-argument
    """
    Celery task to process bulk learner uploads from CSV content.
    CSV columns: username (or email), optional active (defaults to True)
    """
    User = get_user_model()
    created = []
    failed = []
    csv_file = StringIO(csv_content)
    reader = csv.DictReader(csv_file)
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
        created.append({"user_id": user.id, "username": user.username, "email": user.email, "active": obj.active})
    return {"created": created, "failed": failed}
