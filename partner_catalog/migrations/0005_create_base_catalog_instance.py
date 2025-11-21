# This migration creates the BaseCatalog instance using settings values.
# Generated manually

from django.conf import settings
from django.db import migrations


def create_base_catalog_instance(apps, schema_editor):  # pylint: disable=unused-argument
    """
    Create the BaseCatalog instance using values from settings.
    """
    BaseCatalog = apps.get_model('partner_catalog', 'BaseCatalog')

    slug = getattr(settings, 'PARTNER_CATALOG_BASE_CATALOG_SLUG', 'base-catalog')
    name = getattr(settings, 'PARTNER_CATALOG_BASE_CATALOG_NAME', 'Base Catalog')

    BaseCatalog.objects.get_or_create(
        slug=slug,
        defaults={'name': name}
    )


def delete_base_catalog_instance(apps, schema_editor):  # pylint: disable=unused-argument
    """
    Delete the BaseCatalog instance (for rollback).
    """
    BaseCatalog = apps.get_model('partner_catalog', 'BaseCatalog')

    slug = getattr(settings, 'PARTNER_CATALOG_BASE_CATALOG_SLUG', 'base-catalog')
    BaseCatalog.objects.filter(slug=slug).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('partner_catalog', '0004_basecatalog_basecatalogcourse'),
    ]

    operations = [
        migrations.RunPython(create_base_catalog_instance, delete_base_catalog_instance),
    ]
