from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView, TokenRefreshView
    )
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    # 🔑 JWT Authentication
    path("api/auth/login/",
         TokenObtainPairView.as_view(),
         name="token_obtain_pair"
         ),
    path("api/auth/refresh/",
         TokenRefreshView.as_view(),
         name="token_refresh"
         ),

    # 📦 Core API (Users, Configs, TargetApps, Health, Register)
    path("api/", include("core.urls")),
    # 📖 Swagger / OpenAPI Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]
