"""Shared pytest fixtures for the backend test-suite."""

import os

import pytest


def pytest_configure(config):
    # pytest-django lets an exported DJANGO_SETTINGS_MODULE override pytest.ini.
    # Refuse to run against development/production settings (real databases).
    module = os.environ.get("DJANGO_SETTINGS_MODULE", "")
    if module != "config.settings.test":
        pytest.exit(
            f"Refusing to run tests with DJANGO_SETTINGS_MODULE={module!r}; "
            "unset it or use config.settings.test.",
            returncode=4,
        )


@pytest.fixture(autouse=True)
def _clear_cache():
    """Throttle counters live in the (local-memory) cache and SQLite reuses
    primary keys across rolled-back tests, so clear it for every test."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def make_user(db):
    from apps.users.models import User

    counter = {"n": 0}

    def _make(**extra):
        counter["n"] += 1
        n = counter["n"]
        defaults = {
            "email": f"user{n}@example.com",
            "username": f"user{n}",
            "password": "Str0ng-pass-123",
        }
        defaults.update(extra)
        password = defaults.pop("password")
        return User.objects.create_user(password=password, **defaults)

    return _make


@pytest.fixture
def auth_client():
    """Return a factory producing an APIClient authenticated via the JWT cookie."""
    from django.conf import settings
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken

    def _client(user=None):
        client = APIClient()
        if user is not None:
            token = RefreshToken.for_user(user)
            client.cookies[settings.SIMPLE_JWT["AUTH_COOKIE"]] = str(token.access_token)
            client.cookies[settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"]] = str(token)
        return client

    return _client


@pytest.fixture
def problem_factory(db):
    from apps.problems.models import Problem, Section, TestCase

    counter = {"n": 0}

    def _make(visibility="FREE", is_published=True, samples=1, hidden=2, **extra):
        counter["n"] += 1
        n = counter["n"]
        section, _ = Section.objects.get_or_create(name="ARRAY", defaults={"display_name": "Array"})
        problem = Problem.objects.create(
            slug=extra.pop("slug", f"problem-{n}"),
            title=extra.pop("title", f"Problem {n}"),
            number=extra.pop("number", n),
            difficulty=extra.pop("difficulty", "EASY"),
            statement_md="Add two numbers.",
            visibility=visibility,
            is_published=is_published,
            section=section,
            hints_md=extra.pop("hints_md", "first hint\n---\nsecond hint"),
            starter_code_python="print(sum(map(int, input().split())))",
            **extra,
        )
        for i in range(samples):
            TestCase.objects.create(problem=problem, input_data=f"{i} 1", expected_output=str(i + 1),
                                    is_sample=True, is_hidden=False, order_index=i)
        for j in range(hidden):
            TestCase.objects.create(problem=problem, input_data=f"{j} 100", expected_output=str(j + 100),
                                    is_sample=False, is_hidden=True, order_index=samples + j)
        return problem

    return _make
