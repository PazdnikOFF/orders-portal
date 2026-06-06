from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from apps.integrations.providers import OrgLookupError

from .services import suggest_orgs


# --------------------------------------------------------------------------- #
# Organization suggest by INN — combobox dropdown (HTMX) (TЗ §14)
# --------------------------------------------------------------------------- #
@login_required
@require_http_methods(["POST"])
def org_suggest(request):
    """
    Resolve an INN to a list of organizations (head office + branches, each with
    its КПП), upsert them locally and return a dropdown the user picks from.
    """
    inn = (request.POST.get("inn") or "").strip()
    try:
        orgs = suggest_orgs(inn)
    except OrgLookupError as exc:
        return render(request, "directories/_org_options.html", {"error": str(exc)})
    return render(request, "directories/_org_options.html", {"orgs": orgs})
