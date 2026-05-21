from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    VpnConfigViewSet, TargetAppViewSet,
    health_check, RegisterView, UserViewSet,
    billing, mock_webhook, billing_gateway
)

router = DefaultRouter()
router.register(r'configs', VpnConfigViewSet, basename='config')
router.register(r'target-apps', TargetAppViewSet, basename='target-app')
router.register(r'users', UserViewSet, basename='user')

urlpatterns = [
    path('', include(router.urls)),
    path('health/', health_check, name='health'),
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('billing/', billing, name='billing'),
    path('billing/webhook/', mock_webhook, name='webhook'),
    path("billing/gateway/", billing_gateway, name="billing_gateway"),
]
