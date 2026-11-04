"""Query helpers shared by the metric annotations."""

from django.db.models import Count, IntegerField, QuerySet, Subquery
from django.db.models.functions import Coalesce


def count_subquery(queryset: QuerySet, group_by: str) -> Coalesce:
    """Return a correlated COUNT of ``queryset`` as a scalar subquery (0 when it is empty).

    ``queryset`` is filtered on an ``OuterRef`` and ``group_by`` is the field it is correlated on.
    Counting through a subquery instead of ``Count()`` over a join keeps the outer query free of
    JOINs and GROUP BY: with several join-based counts, the joined rows multiply and every other
    annotation is evaluated once per joined row.

    ``order_by()`` clears any ordering already set on ``queryset``: an explicit ordering would be
    added to the GROUP BY and split the count (the model's ``Meta.ordering`` is ignored by grouped
    queries).
    """
    return Coalesce(
        Subquery(
            queryset.order_by().values(group_by).annotate(n=Count("pk")).values("n")[:1],
            output_field=IntegerField(),
        ),
        0,
    )
