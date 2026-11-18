"""Discussions: counts, anonymity, validation, flagging and moderation."""

from apps.discussions.models import CommentUpvote, DiscussionComment, DiscussionThread, ThreadUpvote


def _thread(problem, author, **extra):
    return DiscussionThread.objects.create(problem=problem, author=author, title="T", content="body", **extra)


def test_counts_are_not_multiplied(problem_factory, make_user, auth_client):
    problem, author = problem_factory(), make_user()
    thread = _thread(problem, author)
    for _ in range(2):
        DiscussionComment.objects.create(thread=thread, author=author, content="c")
    for _ in range(3):
        ThreadUpvote.objects.create(thread=thread, user=make_user())
    client = auth_client()
    for url in ("/api/discuss/threads/", f"/api/discuss/problems/{problem.slug}/threads/"):
        row = client.get(url).json()["results"][0]
        assert (row["comment_count"], row["upvote_count"]) == (2, 3), url
    detail = client.get(f"/api/discuss/threads/{thread.id}/").json()
    assert detail["upvote_count"] == 3 and detail["views"] == 1


def test_anonymous_author_hidden_from_users_visible_to_admin(problem_factory, make_user, auth_client):
    author = make_user(username="realname")
    thread = _thread(problem_factory(), author, is_anonymous=True)
    public = auth_client().get(f"/api/discuss/threads/{thread.id}/").json()
    assert public["created_by"]["username"] == "anonymous"
    admin = auth_client(make_user(role="ADMIN")).get(f"/api/discuss/threads/{thread.id}/").json()
    assert admin["created_by"]["username"] == "realname"


def test_create_thread_and_comment_validation(problem_factory, make_user, auth_client):
    problem, user = problem_factory(), make_user()
    client = auth_client(user)
    assert auth_client().post(f"/api/discuss/problems/{problem.slug}/threads/create/", {"title": "t", "content": "c"},
                              format="json").status_code == 401
    created = client.post(f"/api/discuss/problems/{problem.slug}/threads/create/", {"title": "Q", "content": "How?"}, format="json")
    assert created.status_code == 201
    thread_id = created.json()["id"]
    assert client.post(f"/api/discuss/threads/{thread_id}/comments/create/", {"body_md": "  "}, format="json").status_code == 400

    other_thread = _thread(problem, user)
    foreign_parent = DiscussionComment.objects.create(thread=other_thread, author=user, content="x")
    resp = client.post(f"/api/discuss/threads/{thread_id}/comments/create/", {"body_md": "hi", "parent": foreign_parent.id}, format="json")
    assert resp.status_code == 400
    assert client.post(f"/api/discuss/threads/{thread_id}/comments/create/", {"body_md": "hi"}, format="json").status_code == 201


def test_locked_thread_rejects_comments(problem_factory, make_user, auth_client):
    user = make_user()
    thread = _thread(problem_factory(), user, is_locked=True)
    assert auth_client(user).post(f"/api/discuss/threads/{thread.id}/comments/create/", {"body_md": "x"},
                                  format="json").status_code == 400


def test_upvote_toggle(problem_factory, make_user, auth_client):
    user = make_user()
    thread = _thread(problem_factory(), user)
    client = auth_client(user)
    assert client.post(f"/api/discuss/threads/{thread.id}/upvote/").json()["upvote_count"] == 1
    assert client.post(f"/api/discuss/threads/{thread.id}/upvote/").json()["upvote_count"] == 0
    comment = DiscussionComment.objects.create(thread=thread, author=user, content="c")
    assert client.post(f"/api/discuss/comments/{comment.id}/upvote/").json()["upvotes"] == 1
    assert CommentUpvote.objects.count() == 1


def test_flag_and_moderate_flow(problem_factory, make_user, auth_client):
    author = make_user()
    thread = _thread(problem_factory(), author)
    comment = DiscussionComment.objects.create(thread=thread, author=author, content="spam " * 60)
    assert auth_client(make_user()).post(f"/api/discuss/comments/{comment.id}/flag/").status_code == 200

    admin = auth_client(make_user(role="ADMIN"))
    flags = admin.get("/api/admin/discussions/flags/").json()
    assert flags["count"] == 1 and len(flags["flagged_comments"][0]["body_preview"]) == 200
    assert flags["flagged_comments"][0]["thread_id"] == thread.id

    url = f"/api/discuss/admin/comments/{comment.id}/moderate/"
    assert auth_client(make_user()).patch(url, {"is_hidden": True}, format="json").status_code == 403
    assert admin.patch(url, {"is_hidden": "yes"}, format="json").status_code == 400
    assert admin.patch(url, {"is_hidden": True}, format="json").json() == {"ok": True, "is_hidden": True, "is_flagged": False}
    assert admin.get("/api/admin/discussions/flags/").json()["count"] == 0
    assert auth_client().get(f"/api/discuss/threads/{thread.id}/comments/").json()["count"] == 0
