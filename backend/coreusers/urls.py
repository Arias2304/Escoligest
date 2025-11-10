from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AdminUserViewSet,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterView,
    UserAwareTokenView,
)

router = DefaultRouter()
router.register(r"admin/users", AdminUserViewSet, basename="admin-users")

urlpatterns = [
    path("", include(router.urls)),
    path("register/", RegisterView.as_view(), name="register"),
    path("token/", UserAwareTokenView.as_view(), name="token"),
    path("token/refresh/", UserAwareTokenView.as_view(), name="token_refresh"),
    path("me/", MeView.as_view(), name="me"),
    path(
        "password-reset/request/",
        PasswordResetRequestView.as_view(),
        name="password_reset_request",
    ),
    path(
        "password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
]
