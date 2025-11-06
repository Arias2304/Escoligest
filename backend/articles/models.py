import uuid
from django.db import models
from django.utils import timezone

from coreusers.models import User


class Article(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"

    STATUS_CHOICES = (
        (STATUS_PENDING, "Pendiente"),
        (STATUS_APPROVED, "Aprobado"),
        (STATUS_REJECTED, "Rechazado"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    summary = models.CharField(max_length=500, blank=True)
    content = models.TextField(blank=True)
    external_url = models.URLField(blank=True)
    pdf = models.FileField(upload_to="articles/pdfs/", blank=True, null=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    created_by = models.ForeignKey(
        User, related_name="articles_submitted", on_delete=models.CASCADE
    )
    approved_by = models.ForeignKey(
        User,
        related_name="articles_approved",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    review_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def mark_approved(self, user: User, notes: str = ""):
        self.status = self.STATUS_APPROVED
        self.approved_by = user
        self.published_at = timezone.now()
        self.review_notes = notes or ""
        self.save(
            update_fields=[
                "status",
                "approved_by",
                "published_at",
                "review_notes",
                "updated_at",
            ]
        )

    def mark_rejected(self, user: User, notes: str = ""):
        self.status = self.STATUS_REJECTED
        self.approved_by = user
        self.review_notes = notes
        self.published_at = None
        self.save(
            update_fields=["status", "approved_by", "review_notes", "published_at", "updated_at"]
        )
