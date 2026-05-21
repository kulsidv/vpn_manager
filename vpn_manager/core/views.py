import uuid
from django.shortcuts import render
from rest_framework import generics, viewsets, status, permissions
from rest_framework.decorators import api_view, permission_classes, action
from django.contrib.auth import get_user_model
from rest_framework.response import Response
from django.utils import timezone
from .models import VpnConfig, TargetApp, Subscription
from .serializers import (
    VpnConfigSerializer,
    TargetAppSerializer,
    UserRegistrationSerializer,
    UserSerializer,
)

User = get_user_model()


class VpnConfigViewSet(viewsets.ModelViewSet):
    serializer_class = VpnConfigSerializer

    def get_queryset(self):
        return VpnConfig.objects.filter(user=self.request.user).order_by(
            "priority", "created_at"
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["patch"])
    def activate(self, request, pk=None):
        config = self.get_object()
        VpnConfig.objects.filter(user=request.user, is_active=True).update(
            is_active=False
        )
        config.is_active = True
        config.save()
        return Response({"status": "activated", "id": config.id})


class TargetAppViewSet(viewsets.ModelViewSet):
    serializer_class = TargetAppSerializer

    def get_queryset(self):
        return TargetApp.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def health_check(request):
    return Response(
        {
            "status": "ok",
            "timestamp": timezone.now().isoformat(),
            "version": "1.0.0-mvp",
        }
    )


class RegisterView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]


class UserViewSet(viewsets.GenericViewSet):
    serializer_class = UserSerializer

    def get_queryset(self):
        return User.objects.filter(id=self.request.user.id).select_related(
            "subscription"
        )

    @action(detail=False, methods=["get", "patch", "delete"])
    def me(self, request):
        user = request.user

        if request.method == "GET":
            serializer = self.get_serializer(user)
        elif request.method == "PATCH":
            serializer = self.get_serializer(user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
        elif request.method == "DELETE":
            password = request.data.get("password")
            if not password or not user.check_password(password):
                return Response(status=status.HTTP_400_BAD_REQUEST)

            user.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        return Response(serializer.data)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def billing_gateway(request):
    session_id = request.GET.get("session")
    return render(request, "billing.html", {"session_id": session_id})


@api_view(["POST", "PATCH"])
def billing(request):
    user = request.user
    sub, _ = Subscription.objects.get_or_create(user=user)

    if request.method == "POST":
        if sub.status == "active":
            return Response(
                {"error": "Подписка уже активна"}, status=status.HTTP_400_BAD_REQUEST
            )

        session_id = f"sess_{user.id}_{int(timezone.now().timestamp())}"
        if not sub.gateway_customer_id:
            sub.gateway_customer_id = f"cust_{uuid.uuid4().hex[:8]}"
            sub.gateway_subscription_id = f"sub_{uuid.uuid4().hex[:8]}"
            sub.save(
                update_fields=["gateway_customer_id", "gateway_subscription_id"]
            )
        payment_url = request.build_absolute_uri(
            f"/api/billing/gateway/?session={session_id}"
        )

        return Response(
            {
                "payment_url": payment_url,
                "session_id": session_id,
                "amount": 299,
                "currency": "RUB",
                "interval_days": 30,
            },
            status=status.HTTP_201_CREATED,
        )

    if request.method == "PATCH":
        if sub.status != "active":
            return Response(status=status.HTTP_404_NOT_FOUND)
        sub.status = "inactive"
        sub.save(update_fields=["status", "updated_at"])

        return Response(
            "Подписка отменена, она действует до конца оплаченного периода",
            status=status.HTTP_204_NO_CONTENT,
        )


@api_view(["POST"])
def mock_webhook(request):
    session_id = request.data.get("session_id")
    event_type = request.data.get("type")

    if not session_id or event_type != "payment.succeeded":
        return Response(
            {"error": "invalid_request"}, status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Формат session_id: sess_{user_id}_{timestamp}
        user_id = int(session_id.split("_")[1])
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.get(id=user_id)

        sub, _ = Subscription.objects.get_or_create(user=user)

        sub.status = "active"
        sub.current_period_end = timezone.now() + timezone.timedelta(days=30)
        sub.renewal_count += 1
        sub.save(
            update_fields=[
                "status",
                "current_period_end",
                "renewal_count",
                "updated_at",
            ]
        )

        return Response(
            {
                "status": "success",
                "message": "Подписка активирована",
                "expires_at": sub.current_period_end.isoformat(),
            },
            status=status.HTTP_200_OK,
        )

    except (IndexError, ValueError, User.DoesNotExist):
        return Response(
            {"error": "invalid_session"}, status=status.HTTP_400_BAD_REQUEST
        )
