"""Models for managing course catalogs and access for corporate partners."""


from django.contrib.auth import get_user_model
from django.db import models

from corporate_partner_access.edxapp_wrapper.course_module import course_overview


class CorporatePartner(models.Model):
    """Company that manages one or more course catalogs."""

    id = models.AutoField(primary_key=True)
    code = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to="partner_logos/", blank=True, null=True)
    homepage_url = models.URLField(blank=True, null=True)

    class Meta:
        verbose_name = "Corporate Partner"
        verbose_name_plural = "Corporate Partners"
        ordering = ["name"]

    def __str__(self):
        return f"<CorporatePartner: {self.name} (Code: {self.code})>"


class CorporatePartnerCatalogEmailRegex(models.Model):
    """Regex pattern for validating emails for a partner's catalog."""

    id = models.AutoField(primary_key=True)
    catalog = models.ForeignKey(
        "CorporatePartnerCatalog",
        on_delete=models.CASCADE,
        related_name="email_regexes",
    )
    regex = models.CharField(
        max_length=255, help_text="Regex pattern for email validation."
    )

    def __str__(self):
        return (
            f"<CorporatePartnerCatalogEmailRegex: {self.catalog.name} - {self.regex}>"
        )


class CorporatePartnerCatalogCourse(models.Model):
    """Pivot table linking catalogs to courses with ordering."""

    id = models.AutoField(primary_key=True)
    catalog = models.ForeignKey("CorporatePartnerCatalog", on_delete=models.CASCADE)
    course_overview = models.ForeignKey(course_overview(), on_delete=models.CASCADE)
    position = models.PositiveIntegerField(
        default=0, help_text="Ordering of the course within the catalog."
    )

    class Meta:
        verbose_name = "Corporate Partner Catalog Course"
        verbose_name_plural = "Corporate Partner Catalog Courses"
        unique_together = ("catalog", "course_overview")
        ordering = ["position"]

    def __str__(self):
        return f"<CorporatePartnerCatalogCourse: {self.course_overview.display_name}>"  # pylint: disable=no-member


class CorporatePartnerCatalogLearner(models.Model):
    """Pivot table linking catalogs to users with active status."""

    id = models.AutoField(primary_key=True)
    catalog = models.ForeignKey("CorporatePartnerCatalog", on_delete=models.CASCADE)
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Corporate Partner Catalog Learner"
        verbose_name_plural = "Corporate Partner Catalog Learners"
        unique_together = ("catalog", "user")

    def __str__(self):
        # pylint: disable=no-member
        return (
            f"<CorporatePartnerCatalogLearner: {self.user.username} in {self.catalog.name}>"
        )
