"""
Service layer for handling invitation status transitions and persistence.

This module provides the InvitationService class, which encapsulates business logic
for updating the status of CatalogCourseEnrollmentAllowed invitations, including
timestamp management and atomic database updates. It delegates event emission to
Django model signals, ensuring side effects are handled consistently elsewhere.
"""
