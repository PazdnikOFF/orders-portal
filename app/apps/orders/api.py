"""REST API for orders (amendment §10). Auth required; respects role visibility."""
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.response import Response

from django.core.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import Role, User
from apps.directories.services import resolve_distributor, upsert_organization
from apps.integrations.providers import OrgLookupError

from .models import Order, Status
from .services import (
    change_status,
    create_order,
    update_order,
    visible_orders,
)


def _resolve_orgs(data: dict) -> dict:
    """Translate INN-based API input into the instances services expect.

    Distributor is resolved from the admin-managed directory (NOT auto-created);
    potential user / participants are upserted from the provider as before.
    """
    cleaned = dict(data)
    cleaned["distributor_org"] = resolve_distributor(data["distributor_inn"])
    if "trading_org_inn" in data:
        inn = (data["trading_org_inn"] or "").strip()
        cleaned["trading_org"] = upsert_organization(inn) if inn else None
    cleaned["potential_user_org"] = upsert_organization(data["potential_user_inn"])
    cleaned["participant_orgs"] = [upsert_organization(i) for i in data.get("participant_inns", [])]
    return cleaned


class OrderReadSerializer(serializers.ModelSerializer):
    order_code = serializers.CharField(read_only=True)
    manager = serializers.CharField(source="manager.short_name", read_only=True)
    distributor = serializers.CharField(source="distributor.display_name", read_only=True)
    trading_org = serializers.SerializerMethodField()
    potential_user = serializers.CharField(source="potential_user.display_name", read_only=True)
    participants = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id", "order_number", "order_code", "manager", "distributor",
            "trading_org", "potential_user", "participants", "kit", "request_date",
            "forecast_date", "status", "status_display", "file_url",
            "created_at", "updated_at",
        ]

    def get_trading_org(self, obj):
        return obj.trading_org.display_name if obj.trading_org else None

    def get_participants(self, obj):
        return [o.display_name for o in obj.participants.all()]

    def get_file_url(self, obj):
        f = obj.active_file
        request = self.context.get("request")
        if not f:
            return None
        url = f.serve_url
        return request.build_absolute_uri(url) if request else url


class OrderWriteSerializer(serializers.Serializer):
    manager = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=Role.MANAGER, is_active=True)
    )
    distributor_inn = serializers.CharField(max_length=12)
    trading_org_inn = serializers.CharField(
        max_length=12, required=False, allow_blank=True, default=""
    )
    potential_user_inn = serializers.CharField(max_length=12)
    participant_inns = serializers.ListField(
        child=serializers.CharField(max_length=12), required=False, default=list
    )
    kit = serializers.CharField(max_length=500)
    forecast_date = serializers.DateField()
    status = serializers.ChoiceField(choices=Status.choices, required=False, default=Status.PLANNED)


class OrderViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        return visible_orders(self.request.user)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return OrderWriteSerializer
        return OrderReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = OrderWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            order = create_order(request, _resolve_orgs(serializer.validated_data))
        except PermissionDenied as exc:
            raise DRFPermissionDenied(str(exc))
        except OrgLookupError as exc:
            return Response({"detail": str(exc)}, status=422)
        return Response(OrderReadSerializer(order, context={"request": request}).data,
                        status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        order = self.get_object()
        serializer = OrderWriteSerializer(data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        try:
            update_order(request, order, _resolve_orgs(serializer.validated_data))
        except PermissionDenied as exc:
            raise DRFPermissionDenied(str(exc))
        except OrgLookupError as exc:
            return Response({"detail": str(exc)}, status=422)
        except ValidationError as exc:
            return Response({"detail": exc.messages}, status=400)
        order.refresh_from_db()
        return Response(OrderReadSerializer(order, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def status(self, request, pk=None):
        order = self.get_object()
        try:
            change_status(request, order, request.data.get("status"))
        except PermissionDenied as exc:
            raise DRFPermissionDenied(str(exc))
        except ValidationError as exc:
            return Response({"detail": exc.messages}, status=400)
        return Response(OrderReadSerializer(order, context={"request": request}).data)
