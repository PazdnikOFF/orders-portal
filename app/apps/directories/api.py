"""REST API for reference data (amendment §10 — получение справочников)."""
from rest_framework import mixins, viewsets
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.integrations.providers import OrgLookupError

from .models import Employee, Organization
from .services import upsert_organization


class EmployeeSerializer(serializers.ModelSerializer):
    short_name = serializers.CharField(read_only=True)

    class Meta:
        model = Employee
        fields = ["id", "last_name", "first_name", "middle_name", "type", "is_active", "short_name"]


class OrganizationSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = Organization
        fields = [
            "id", "inn", "name", "full_name", "kpp", "ogrn",
            "address", "status", "source", "updated_at", "display_name",
        ]


class EmployeeViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = EmployeeSerializer

    def get_queryset(self):
        qs = Employee.objects.all()
        emp_type = self.request.query_params.get("type")
        if emp_type:
            qs = qs.filter(type=emp_type)
        if self.request.query_params.get("active") == "1":
            qs = qs.filter(is_active=True)
        return qs


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
