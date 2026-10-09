from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify


class Member(models.Model):
    name = models.CharField(max_length=100)
    email = models.TextField(blank=True)
    phone = models.TextField(blank=True)
    region = models.ForeignKey(
        "Region",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="members",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Region(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.name = self.name.strip()
        self.slug = slugify(self.name)
        if not self.slug:
            raise ValidationError(
                {"name": "Region name must contain a letter or number."}
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
