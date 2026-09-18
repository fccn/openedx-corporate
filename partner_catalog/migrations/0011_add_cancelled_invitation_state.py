import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partner_catalog', '0010_basecatalogcourse_unique_base_catalog_course'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='cataloglearnerinvitation',
            name='cancelled_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='cataloglearnerinvitation',
            name='cancelled_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='cancelled_learner_invitations',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddIndex(
            model_name='cataloglearnerinvitation',
            index=models.Index(fields=['cancelled_at'], name='partner_cat_cancell_idx'),
        ),
        migrations.AddConstraint(
            model_name='cataloglearnerinvitation',
            constraint=models.CheckConstraint(
                name='cla_cancelled_not_accepted',
                check=models.Q(cancelled_at__isnull=True) | models.Q(accepted_at__isnull=True),
            ),
        ),
    ]
