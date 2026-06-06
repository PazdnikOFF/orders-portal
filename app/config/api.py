"""Aggregated REST API router (amendment §10 — заказы, файлы, справочники)."""
from rest_framework.routers import DefaultRouter

from apps.directories.api import OrganizationViewSet
from apps.orders.api import OrderViewSet

router = DefaultRouter()
router.register("orders", OrderViewSet, basename="order")
router.register("organizations", OrganizationViewSet, basename="organization")

urlpatterns = router.urls
