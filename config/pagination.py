from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Default API pagination: ?page=N, optional ?page_size=M (capped)."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class LargePagination(StandardPagination):
    """For cheap, bounded catalogue lists (problems, tags, sections) that the UI
    renders in full, e.g. the grouped problem list and tag sidebar."""

    max_page_size = 1000
