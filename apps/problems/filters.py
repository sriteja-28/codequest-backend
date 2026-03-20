import django_filters
from .models import Problem, Tag, Section


class ProblemFilter(django_filters.FilterSet):
    difficulty = django_filters.CharFilter(field_name="difficulty", lookup_expr="iexact")
    section = django_filters.CharFilter(field_name="section__name", lookup_expr="iexact")
    topic = django_filters.CharFilter(method="filter_topic")
    company = django_filters.CharFilter(method="filter_company")
    search = django_filters.CharFilter(field_name="title", lookup_expr="icontains")
    solved = django_filters.BooleanFilter(method="filter_solved")

    class Meta:
        model = Problem
        fields = ["difficulty", "section", "topic", "company", "search"]

    def filter_topic(self, queryset, name, value):
        return queryset.filter(tags__slug=value, tags__tag_type="TOPIC")

    def filter_company(self, queryset, name, value):
        return queryset.filter(tags__slug=value, tags__tag_type="COMPANY")

    def filter_solved(self, queryset, name, value):
        request = self.request
        if not request or not request.user.is_authenticated:
            return queryset
        solved_ids = request.user.solved_problems.values_list("problem_id", flat=True)
        if value:
            return queryset.filter(id__in=solved_ids)
        return queryset.exclude(id__in=solved_ids)