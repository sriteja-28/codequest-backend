"""Function-only signature and starter-code generation."""

import pytest

from apps.problems import codegen
from apps.problems.models import Problem

SIGNATURE = {
    "name": "twoSum",
    "params": [
        {"name": "nums", "type": "int[]"},
        {"name": "target", "type": "int"},
    ],
    "return_type": "int[]",
}


def test_signature_validation_and_normalization():
    assert codegen.validate_signature(SIGNATURE) == SIGNATURE
    assert codegen.parse_type("string[][]") == ("string", 2)
    with pytest.raises(codegen.SignatureError):
        codegen.validate_signature({"name": "f", "params": [], "return_type": "void"})
    with pytest.raises(codegen.SignatureError):
        codegen.validate_signature({
            "name": "f",
            "params": [{"name": "x", "type": "long[][]"}],
            "return_type": "int",
        })


def test_starter_code_has_no_stdin_or_main_boilerplate():
    python = codegen.starter_code(SIGNATURE, "python")
    assert "class Solution:" in python and "def twoSum" in python
    assert "input(" not in python and "__main__" not in python

    cpp = codegen.starter_code(SIGNATURE, "cpp")
    assert "class Solution" in cpp and "twoSum" in cpp
    assert "int main(" not in cpp and "cin" not in cpp

    java = codegen.starter_code(SIGNATURE, "java")
    assert "class Solution" in java and "twoSum" in java
    assert "public class" not in java and "main(" not in java

    javascript = codegen.starter_code(SIGNATURE, "javascript")
    assert "var twoSum" in javascript
    assert "readFileSync" not in javascript


def test_starter_defaults_match_return_type():
    assert 'return "";' in codegen.starter_code({**SIGNATURE, "return_type": "string"}, "java")
    assert "return false;" in codegen.starter_code({**SIGNATURE, "return_type": "bool"}, "cpp")
    assert "return new int[]{};" in codegen.starter_code({**SIGNATURE, "return_type": "int[]"}, "java")


def test_format_input_uses_parameter_names():
    assert codegen.format_input(SIGNATURE, '{"nums": [2, 7, 11, 15], "target": 9}') == (
        "nums = [2, 7, 11, 15], target = 9"
    )
    assert codegen.format_input(SIGNATURE, "1 2") == "1 2"
    assert codegen.format_input(SIGNATURE, '{"s": "()"}') == '{"s": "()"}'


@pytest.mark.django_db
def test_problem_detail_generates_starter_and_display_input(problem_factory, auth_client):
    problem = problem_factory(samples=1)
    problem.function_signature = SIGNATURE
    problem.starter_code_python = ""
    problem.save(update_fields=["function_signature", "starter_code_python"])
    problem.test_cases.update(input_data='{"nums": [2, 7], "target": 9}')

    data = auth_client().get(f"/api/problems/{problem.slug}/").json()
    assert data["function_signature"] == SIGNATURE
    assert "class Solution" in data["starter_code_python"]
    assert data["sample_test_cases"][0]["display_input"] == "nums = [2, 7], target = 9"


@pytest.mark.django_db
def test_model_clean_rejects_invalid_signature(problem_factory):
    from django.core.exceptions import ValidationError

    problem = problem_factory()
    problem.function_signature = {"name": "bad name", "params": [], "return_type": "int"}
    with pytest.raises(ValidationError):
        problem.full_clean()


@pytest.mark.django_db
def test_admin_serializer_accepts_signature(problem_factory):
    from apps.problems.serializers import ProblemAdminSerializer

    problem = problem_factory()
    serializer = ProblemAdminSerializer(
        problem,
        data={"function_signature": SIGNATURE, "compare_mode": "UNORDERED"},
        partial=True,
    )
    assert serializer.is_valid(), serializer.errors
    updated = serializer.save()
    assert updated.function_signature == SIGNATURE
    assert updated.compare_mode == Problem.CompareMode.UNORDERED
