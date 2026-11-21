from typing import Any

from django.db import models
from django.utils.text import slugify

from apps.core.models import Country, Sector, TimeStampedModel


class Funder(TimeStampedModel):
    class FunderType(models.TextChoices):
        FOUNDATION = "foundation", "Foundation"
        GOVERNMENT = "government", "Government"
        MULTILATERAL = "multilateral", "Multilateral"
        CORPORATE = "corporate", "Corporate"
        EMBASSY = "embassy", "Embassy"
        BANK = "bank", "Bank"
        UNIVERSITY = "university", "University"
        OTHER = "other", "Other"

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=220, unique=True)
    funder_type = models.CharField(
        max_length=20,
        choices=FunderType.choices,
        default=FunderType.OTHER,
    )
    website = models.URLField(blank=True)
    description = models.TextField(blank=True)
    countries = models.ManyToManyField(Country, blank=True, related_name="funders")
    sectors = models.ManyToManyField(Sector, blank=True, related_name="funders")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["funder_type", "is_active"], name="funder_type_active_idx")]

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name
