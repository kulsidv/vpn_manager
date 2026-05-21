from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    is_subscribed = models.BooleanField(default=False, editable=False)

    class Meta:
        verbose_name = "пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return super().__str__()

    def save(self, *args, **kwargs):
        sub = self.subscription
        self.is_subscribed = bool(
            sub and sub.status == 'active'
            and sub.current_period_end > timezone.now()
        )
        super().save(*args, **kwargs)


class VpnConfig(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Пользователь",
        related_name="vpn_configs",
    )
    config_text = models.TextField(
        "Конфигурация", help_text="Полный текст конфигурации WireGuard"
    )
    priority = models.IntegerField("Приоритет")
    is_active = models.BooleanField("Активен", default=False)
    created_at = models.DateTimeField("Добавлен", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлен", auto_now=True)

    class Meta:
        verbose_name = "настройки VPN"
        verbose_name_plural = "Настройки VPN"
        ordering = ["priority", "created_at"]

    def __str__(self):
        return f"{self.user}.{self.priority}"


class TargetApp(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Пользователь",
        related_name="target_apps",
    )
    package_name = models.CharField("Название пакета", max_length=255)
    created_at = models.DateTimeField("Добавлен", auto_now_add=True)

    class Meta:
        verbose_name = "целевое приложение"
        verbose_name_plural = "Целевые приложения"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "package_name"], name="unique_user_app_pair"
            )
        ]


class Subscription(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="subscription",
        unique=True
    )
    gateway_customer_id = models.CharField(
        "ID клиента в шлюзе", max_length=100, blank=True, null=True
    )
    gateway_subscription_id = models.CharField(
        "ID подписки в шлюзе", max_length=100, blank=True, null=True
    )
    current_period_end = models.DateTimeField(
        "Конец оплаченного периода", null=True, blank=True
    )
    renewal_count = models.PositiveIntegerField("Количество продлений", default=0)
    STATUS_CHOICES = [
        ('inactive', 'Неактивна'),
        ('active', 'Активна'),
        ('in progress', 'Оформляется')
    ]
    status = models.CharField(
        "Статус", max_length=12, choices=STATUS_CHOICES, default="in progress"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "подписка"
        verbose_name_plural = "Подписка"
