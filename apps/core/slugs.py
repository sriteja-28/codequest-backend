"""Slugs for admin-created rows: generated from a title when left blank, made unique."""

from django.utils.text import slugify


def unique_slug(model, source: str, *, field: str = "slug", max_length: int | None = None, exclude_pk=None) -> str:
    """`source` slugified, suffixed -2, -3, ... until no other `model` row uses it."""
    max_length = max_length or model._meta.get_field(field).max_length
    base = (slugify(source) or "item")[:max_length].strip("-") or "item"
    queryset = model.objects.all()
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)
    candidate, counter = base, 2
    while queryset.filter(**{field: candidate}).exists():
        suffix = f"-{counter}"
        candidate = f"{base[: max_length - len(suffix)].rstrip('-')}{suffix}"
        counter += 1
    return candidate
