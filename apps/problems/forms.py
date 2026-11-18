"""Django admin validation matches the dashboard editors."""
from django import forms
from rest_framework.exceptions import ValidationError as APIValidationError

from .models import Section, TestCase
from .serializers import SectionAdminSerializer, TestCaseAdminSerializer


class SectionAdminForm(forms.ModelForm):
    class Meta:
        model = Section
        fields = "__all__"

    def clean_prerequisites(self):
        rows = self.cleaned_data["prerequisites"]
        try:
            return SectionAdminSerializer(instance=self.instance).validate_prerequisite_ids(list(rows))
        except APIValidationError as exc:
            raise forms.ValidationError([str(item) for item in exc.detail]) from exc


class TestCaseAdminForm(forms.ModelForm):
    class Meta:
        model = TestCase
        fields = "__all__"

    def clean(self):
        data = super().clean()
        problem = data.get("problem")
        if problem is None and self.instance.problem_id:
            problem = self.instance.problem
        if problem is not None:
            try:
                TestCaseAdminSerializer(instance=self.instance, context={"problem": problem}).validate(data)
            except APIValidationError as exc:
                for name, errors in exc.detail.items():
                    self.add_error(name, [str(error) for error in errors])
        return data
