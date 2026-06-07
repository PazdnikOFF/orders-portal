"""Session timeout (TЗ §1) and display-timezone activation."""
import zoneinfo

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

LAST_ACTIVITY_KEY = "_last_activity"


class TimezoneMiddleware:
    """
    Activates settings.DISPLAY_TIME_ZONE for the duration of each request.
    Storage stays UTC (TЗ §10); templates show local time automatically
    (Django uses the active timezone for filters like |date and |time).
    """

    def __init__(self, get_response):
        self.get_response = get_response
        try:
            self.tz = zoneinfo.ZoneInfo(settings.DISPLAY_TIME_ZONE)
        except Exception:                                 # pragma: no cover
            self.tz = timezone.utc

    def __call__(self, request):
        timezone.activate(self.tz)
        try:
            return self.get_response(request)
        finally:
            timezone.deactivate()


class SessionTimeoutMiddleware:
    """
    On every authenticated request, compares "now" with the timestamp of the
    last activity. If the idle gap exceeds SESSION_IDLE_TIMEOUT the user is
    logged out and redirected to the login page (auto-relogin, TЗ §17).

    Works together with SESSION_COOKIE_AGE / SESSION_SAVE_EVERY_REQUEST, which
    expire the cookie itself; this middleware additionally guarantees a clean
    redirect + flash message instead of a silently empty page.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.timeout = settings.SESSION_IDLE_TIMEOUT.total_seconds()

    def __call__(self, request):
        if request.user.is_authenticated:
            now = timezone.now().timestamp()
            last = request.session.get(LAST_ACTIVITY_KEY)
            if last is not None and (now - last) > self.timeout:
                logout(request)
                messages.info(
                    request,
                    "Сессия завершена по истечении 45 минут. Войдите снова.",
                )
                login_url = reverse(settings.LOGIN_URL)
                return redirect(f"{login_url}?next={request.path}")
            request.session[LAST_ACTIVITY_KEY] = now
        return self.get_response(request)
