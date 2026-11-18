"""Audit trail for staff changes (one table: AdminLog).

Writers:
  * admin dashboard API: `AuditedViewSetMixin` on admin viewsets (create /
    update with a field diff / delete, in the same transaction as the change),
    or `record()` from custom views (bans, plan changes, settings, moderation);
  * Django admin: every LogEntry it writes is mirrored (`mirror_django_admin`,
    connected in AdminPanelConfig.ready), so both admin UIs share one history;
  * system jobs such as scheduled contest finalization (admin empty, source "system").
"""

import datetime
import decimal
import json
import uuid

from django.db import transaction

MAX_VALUE_CHARS = 120
SKIP_FIELDS = frozenset({"created_at", "updated_at", "password", "last_login"})
VERBS = {"CREATE": "Created", "UPDATE": "Updated", "DELETE": "Deleted"}


def object_type_of(obj_or_model) -> str:
    """'problem', 'test_case', 'contest_participant', ... (verbose name, snake case)."""
    return str(obj_or_model._meta.verbose_name).replace(" ", "_")


def label_of(obj_or_model) -> str:
    return str(obj_or_model._meta.verbose_name)


def _shorten(text: str) -> str:
    return text if len(text) <= MAX_VALUE_CHARS else text[: MAX_VALUE_CHARS - 1] + "…"


def plain(value):
    """A short JSON-safe rendering of a field value for the audit `changes`."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, (decimal.Decimal, uuid.UUID)):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value[:50]]
    if isinstance(value, dict):
        return _shorten(json.dumps(value, default=str, sort_keys=True, ensure_ascii=False))
    return _shorten(str(value))


def snapshot(instance) -> dict:
    """Comparable field values (foreign keys as ids, many-to-many as sorted ids)."""
    data = {}
    for field in instance._meta.concrete_fields:
        if field.name not in SKIP_FIELDS:
            data[field.name] = field.value_from_object(instance)
    if instance.pk is not None:
        for field in instance._meta.many_to_many:
            data[field.name] = sorted(getattr(instance, field.name).values_list("pk", flat=True))
    return data


def diff(before: dict, after: dict) -> dict:
    """{"field": [old, new]} for every value that changed."""
    return {
        key: [plain(before.get(key)), plain(after.get(key))]
        for key in sorted(set(before) | set(after))
        if before.get(key) != after.get(key)
    }


def record(*, actor=None, action, obj=None, object_type=None, object_id=None, object_repr=None,
           description="", changes=None, source=None):
    """Write one AdminLog row. `obj` fills type/id/repr unless given explicitly."""
    from .models import AdminLog

    if obj is not None:
        object_type = object_type or object_type_of(obj)
        object_id = obj.pk if object_id is None else object_id
        object_repr = str(obj) if object_repr is None else object_repr
    if actor is not None and not getattr(actor, "is_authenticated", False):
        actor = None
    return AdminLog.objects.create(
        admin=actor,
        action=action,
        object_type=(object_type or "")[:50],
        object_id="" if object_id is None else str(object_id)[:64],
        object_repr=(object_repr or "")[:200],
        description=description,
        changes=changes or {},
        source=source or ("api" if actor else "system"),
    )


class AuditedViewSetMixin:
    """Log create / update / destroy of an admin ModelViewSet.

    Hooks:
      * `create_kwargs()`  extra fields for serializer.save() on create (e.g. the
        parent object taken from the URL);
      * `audit_snapshot()` include related data that is not a model field (e.g.
        the ordered problems of a practice list) in the update diff.
    A viewset may override perform_destroy to refuse a delete, then call super().
    """

    def create_kwargs(self) -> dict:
        return {}

    def audit_snapshot(self, instance) -> dict:
        return snapshot(instance)

    def perform_create(self, serializer):
        with transaction.atomic():
            serializer.save(**self.create_kwargs())
            obj = serializer.instance
            record(actor=self.request.user, action="CREATE", obj=obj,
                   description=f"Created {label_of(obj)} '{_shorten(str(obj))}'")

    def perform_update(self, serializer):
        with transaction.atomic():
            before = self.audit_snapshot(serializer.instance)
            serializer.save()
            obj = serializer.instance
            changes = diff(before, self.audit_snapshot(obj))
            if changes:
                record(actor=self.request.user, action="UPDATE", obj=obj, changes=changes,
                       description=f"Updated {label_of(obj)} '{_shorten(str(obj))}': {', '.join(changes)}")

    def perform_destroy(self, instance):
        object_type, pk, text, label = object_type_of(instance), instance.pk, str(instance), label_of(instance)
        with transaction.atomic():
            instance.delete()
            record(actor=self.request.user, action="DELETE", object_type=object_type, object_id=pk,
                   object_repr=text, description=f"Deleted {label} '{_shorten(text)}'")


def audited_update(*, actor, instance, apply, description=None, action="UPDATE", object_type=None):
    """Run `apply()` (which saves `instance`) and log the resulting field diff.
    Returns the changes; nothing is logged when nothing changed."""
    with transaction.atomic():
        before = snapshot(instance)
        apply()
        changes = diff(before, snapshot(instance))
        if changes:
            record(actor=actor, action=action, obj=instance, object_type=object_type, changes=changes,
                   description=description or f"Updated {label_of(instance)} '{_shorten(str(instance))}': "
                                              f"{', '.join(changes)}")
        return changes


def mirror_django_admin(sender, instance, created, **kwargs):
    """post_save receiver for django.contrib.admin LogEntry."""
    from django.contrib.admin.models import ADDITION, CHANGE, DELETION

    if not created:
        return
    action = {ADDITION: "CREATE", CHANGE: "UPDATE", DELETION: "DELETE"}.get(instance.action_flag)
    if action is None:
        return
    model = instance.content_type.model_class() if instance.content_type_id else None
    message = instance.get_change_message()
    verb = {"CREATE": "Added", "UPDATE": "Changed", "DELETE": "Deleted"}[action]
    record(
        actor=instance.user,
        action=action,
        object_type=object_type_of(model) if model else "unknown",
        object_id=instance.object_id or "",
        object_repr=instance.object_repr,
        description=f"{verb} in Django admin" + (f": {message}" if message else ""),
        source="django",
    )
