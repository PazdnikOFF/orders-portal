"""REST API for reference data (amendment §10 — получение справочников)."""
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.integrations.providers import OrgLookupError

from .models import Organization
from .services import upsert_organization


class OrganizationSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = Organization
        fields = [
            "id", "inn", "name", "full_name", "kpp", "ogrn",
            "address", "status", "source", "updated_at", "display_name",
        ]


class OrganizationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = OrganizationSerializer
    queryset = Organization.objects.all()

    @action(detail=False, methods=["post"])
    def lookup(self, request):
        """POST {"inn": "..."} -> resolve via provider, upsert, return record."""
        inn = (request.data.get("inn") or "").strip()
        try:
            org = upsert_organization(inn)
        except OrgLookupError as exc:
            return Response({"detail": str(exc)}, status=422)
        return Response(self.get_serializer(org).data)
