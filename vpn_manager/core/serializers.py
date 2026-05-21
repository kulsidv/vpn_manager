from rest_framework import serializers
from .models import VpnConfig, TargetApp, Subscription
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

User = get_user_model()


class SubscriptionToUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = (
            "id",
            "status",
            "current_period_end",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "status",
            "current_period_end",
            "created_at",
            "updated_at",
        )


class UserSerializer(serializers.ModelSerializer):
    subscription = SubscriptionToUserSerializer(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_subscribed",
            "subscription",
        )
        read_only_fields = ("id", "is_subscribed", "subscription")

    def to_internal_value(self, data):
        # Явно отклоняем попытку изменить read_only поля
        read_only = set(self.Meta.read_only_fields)
        forbidden = read_only.intersection(data.keys())
        if forbidden:
            raise serializers.ValidationError(
                {
                    field: "Это поле доступно только для чтения и не может быть изменено через API."
                    for field in forbidden
                }
            )
        return super().to_internal_value(data)


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
        help_text="Минимум 8 символов, не слишком простой",
    )
    password_confirm = serializers.CharField(
        write_only=True, required=True, style={"input_type": "password"}
    )

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "password",
            "password_confirm",
            "is_subscribed",
        )
        read_only_fields = ("id", "is_subscribed")

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Пароли не совпадают."}
            )

        try:
            validate_password(attrs["password"])
        except ValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})

        return attrs

    def create(self, validated_data):
        # Удаляем поле подтверждения, оно не нужно модели
        validated_data.pop("password_confirm")

        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=validated_data["password"],
        )
        return user


class VpnConfigSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = VpnConfig
        fields = (
            "id",
            "user",
            "config_text",
            "priority",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "user")

    def validate(self, attrs):
        # Проверяем ограничение только при создании (POST),
        # а не при обновлении (PATCH)
        if self.instance is None:
            request = self.context.get("request")
            user = request.user
            existing_count = VpnConfig.objects.filter(user=user).count()
            if not user.is_subscribed and existing_count >= 1:
                raise serializers.ValidationError(
                    "Без активной подписки можно хранить только один VPN-конфиг. "
                    "Для добавления новых профилей оформите подписку."
                )
            elif user.is_subscribed and existing_count >= 10:
                raise serializers.ValidationError("Можно добавить только 10 конфигов")
        return attrs


class TargetAppSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = TargetApp
        fields = ("id", "user", "package_name", "created_at")
        read_only_fields = ("id", "user", "created_at")


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = (
            "id",
            "status",
            "current_period_end",
            "renewal_count",
            "gateway_customer_id",
            "gateway_subscription_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "gateway_customer_id",
            "gateway_subscription_id",
        )
