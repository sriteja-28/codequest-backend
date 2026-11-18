"""Courses catalog and lesson progress (B4)."""

from apps.courses.models import Category, Chapter, Course, Lesson, LessonProgress


def make_course(published=True):
    category = Category.objects.create(name="Interview Prep", icon="🎯")
    course = Course.objects.create(
        category=category,
        slug="foundations",
        title="Foundations",
        subtitle="Start here",
        difficulty="BEGINNER",
        is_published=published,
    )
    chapter = Chapter.objects.create(course=course, title="Arrays", order_index=1)
    one = Lesson.objects.create(
        chapter=chapter, slug="arrays-101", title="Arrays 101", order_index=1
    )
    two = Lesson.objects.create(
        chapter=chapter, slug="hash-maps", title="Hash maps", order_index=2
    )
    Lesson.objects.create(
        chapter=chapter, slug="draft", title="Draft", is_published=False, order_index=3
    )
    return category, course, one, two


def test_course_catalog_and_detail(db, auth_client):
    category, course, one, two = make_course()

    categories = auth_client().get("/api/courses/categories/").json()["results"]
    assert categories[0]["slug"] == "interview-prep"
    assert categories[0]["course_count"] == 1

    listing = auth_client().get("/api/courses/").json()["results"]
    assert [c["slug"] for c in listing] == [course.slug]
    assert listing[0]["lesson_count"] == 2
    assert listing[0]["completed_count"] == 0
    assert listing[0]["progress_percent"] == 0.0

    detail = auth_client().get(f"/api/courses/{course.slug}/").json()
    lessons = detail["chapters"][0]["lessons"]
    assert [lesson["slug"] for lesson in lessons] == [one.slug, two.slug]
    assert detail["chapters"][0]["lesson_count"] == 2


def test_unpublished_course_hidden(db, auth_client):
    make_course(published=False)
    assert auth_client().get("/api/courses/").json()["count"] == 0
    assert auth_client().get("/api/courses/foundations/").status_code == 404


def test_lesson_complete_and_uncomplete(make_user, auth_client):
    _, course, lesson, _ = make_course()
    client = auth_client(make_user())

    response = client.post(f"/api/courses/lessons/{lesson.id}/complete/")
    assert response.status_code == 200
    assert response.json()["completed"] is True
    assert response.json()["course"]["completed_count"] == 1
    assert response.json()["course"]["progress_percent"] == 50.0
    assert LessonProgress.objects.filter(lesson=lesson).count() == 1

    # Completing twice is idempotent.
    client.post(f"/api/courses/lessons/{lesson.id}/complete/")
    assert LessonProgress.objects.filter(lesson=lesson).count() == 1

    detail = client.get(f"/api/courses/{course.slug}/").json()
    assert detail["completed_count"] == 1
    assert detail["chapters"][0]["lessons"][0]["is_completed"] is True

    response = client.delete(f"/api/courses/lessons/{lesson.id}/complete/")
    assert response.json()["completed"] is False
    assert response.json()["course"]["completed_count"] == 0
    assert LessonProgress.objects.filter(lesson=lesson).count() == 0


def test_lesson_complete_requires_authentication(db, auth_client):
    _, _, lesson, _ = make_course()
    assert auth_client().post(f"/api/courses/lessons/{lesson.id}/complete/").status_code == 401


def test_lesson_can_link_a_problem(problem_factory, db, auth_client):
    problem = problem_factory()
    _, course, lesson, _ = make_course()
    lesson.problem = problem
    lesson.save(update_fields=["problem"])

    detail = auth_client().get(f"/api/courses/{course.slug}/").json()
    linked = detail["chapters"][0]["lessons"][0]["problem"]
    assert linked["slug"] == problem.slug
    assert linked["difficulty"] == "EASY"
