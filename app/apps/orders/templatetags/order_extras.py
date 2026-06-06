"""Template helpers for table column sorting (keeps current filters)."""
from django import template

register = template.Library()

_DEFAULT_SORT = "request_date"


@register.simple_tag(takes_context=True)
def sort_url(context, field):
    """URL that sorts by `field`, toggling direction if already active."""
    request = context["request"]
    params = request.GET.copy()
    cur_sort = params.get("sort", _DEFAULT_SORT)
    cur_dir = params.get("dir", "desc")
    new_dir = ("asc" if cur_dir == "desc" else "desc") if cur_sort == field else "asc"
    params["sort"] = field
    params["dir"] = new_dir
    params.pop("page", None)
    params.pop("selected", None)
    return "?" + params.urlencode()


@register.simple_tag(takes_context=True)
def sort_arrow(context, field):
    """▲/▼ indicator for the currently active sort column."""
    request = context["request"]
    if request.GET.get("sort", _DEFAULT_SORT) != field:
        return ""
    return " ▼" if request.GET.get("dir", "desc") == "desc" else " ▲"
