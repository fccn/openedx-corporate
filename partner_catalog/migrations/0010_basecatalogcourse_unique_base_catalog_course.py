"""Migration to add a uniqueness constraint on (base_catalog, course_overview) for BaseCatalogCourse."""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Add UniqueConstraint to prevent duplicate BaseCatalogCourse entries."""

    dependencies = [
        ("partner_catalog", "0009_alter_catalogcourseenrollment_course_overview"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="basecatalogcourse",
            constraint=models.UniqueConstraint(
                fields=["base_catalog", "course_overview"],
                name="unique_base_catalog_course",
            ),
        ),
    ]
