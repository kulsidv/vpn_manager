from django.db import transaction
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
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return VpnConfig.objects.filter(user=self.request.user).order_by(
            "priority", "created_at"
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class TargetAppViewSet(viewsets.ModelViewSet):
    serializer_class = TargetAppSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

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

        # тут должна быть отправка запроса в платежную систему,
        # чтобы она прекратила реккурентные списания

        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@transaction.atomic
def webhook(request):
    session_id = request.data.get("session_id")
    event_type = request.data.get("type")
    if not session_id or not event_type:
        return Response(
            {"error": "invalid_payload"}, status=status.HTTP_400_BAD_REQUEST
        )
    try:
        user_id = int(session_id.split("_")[1])
        User = get_user_model()
        user = User.objects.get(id=user_id)
    except (IndexError, ValueError, User.DoesNotExist):
        return Response({"status": "ignored"}, status=status.HTTP_200_OK)

    sub, _ = Subscription.objects.get_or_create(user=user)

    if event_type == "payment.succeeded":
        if sub.status == "active":
            # Идемпотентность: шлюзы шлют один webhook 3-5 раз при сетевых ошибках
            return Response(
                {"status": "already_processed"}, status=status.HTTP_200_OK
                )

        sub.status = "active"
        sub.current_period_end = timezone.now() + timezone.timedelta(days=30)
        sub.renewal_count += 1
    else:
        sub.status = "inactive"

    sub.save(
        update_fields=[
            "status", "current_period_end", "renewal_count", "updated_at"
            ]
    )

    return Response(
        {"status": "processed", "event": event_type, "subscription_status": sub.status},
        status=status.HTTP_200_OK,
    )
