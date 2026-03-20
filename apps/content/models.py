from django.db import models
from django.utils.text import slugify


class ContentPage(models.Model):
    """Static content pages (About, FAQ, Terms, etc.)."""
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
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
