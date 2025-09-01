"""
Helpers for email normalization and related utilities in the corporate_partner_access app.

This module provides functions for consistent handling of email addresses,
such as normalization for case-insensitive comparison and storage.
"""

from __future__ import annotations

from typing import Optional


def normalize_email(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return value.strip().lower()
