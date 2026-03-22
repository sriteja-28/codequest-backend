from django.db import models
from django.utils.text import slugify


class ContentPage(models.Model):
    # storing static pages
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    title = models.CharField(max_length=200)
    content = models.TextField()

    published = models.BooleanField(default=False)
    order_index = models.PositiveSmallIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "content_pages"
        ordering = ["order_index", "slug"]

    def save(self, *args, **kwargs):
        # generating slug from title if missing
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class AdPlacement(models.Model):
    # defining ad slots
    key = models.CharField(max_length=100, unique=True)
    position = models.CharField(max_length=100)

    # adding missing fields from seed
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    max_per_page = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "ad_placements"

    def __str__(self):
        return self.key


class AdCreative(models.Model):
    # storing ad content
    name = models.CharField(max_length=200)

    html_snippet = models.TextField(blank=True)
    image_url = models.URLField(blank=True)
    link_url = models.URLField()

    # adding time window fields
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)
    

    plan_target = models.CharField(
        max_length=10,
        choices=[("FREE", "FREE"), ("PRO", "PRO")],
        default="FREE"
    )

    priority = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    placement = models.ForeignKey(
        AdPlacement,
        related_name="creatives",
        on_delete=models.CASCADE
    )

    class Meta:
        db_table = "ad_creatives"
        ordering = ["-priority"]

    def __str__(self):
        return self.name


class FeatureFlag(models.Model):
    # feature toggles
    key = models.CharField(max_length=100, unique=True)
    value = models.BooleanField(default=False)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "feature_flags"

    def __str__(self):
        return self.key