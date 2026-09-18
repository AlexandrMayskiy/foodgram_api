from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import CheckConstraint, F, Q, UniqueConstraint


class User(AbstractUser):
    """Кастомная модель пользователя с авторизацией по email."""

    email = models.EmailField("Электронная почта", max_length=254, unique=True)
    first_name = models.CharField("Имя", max_length=150)
    last_name = models.CharField("Фамилия", max_length=150)
    avatar = models.ImageField(
        "Аватар",
        upload_to="users/avatars/",
        blank=True,
        null=True,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[tuple] = ("username", "first_name", "last_name")

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ("username",)

    def __str__(self):
        return self.username


class Follow(models.Model):
    """Модель связи для подписок на авторов рецептов."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="follower",
        verbose_name="Подписчик",
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="following",
        verbose_name="Автор",
    )

    class Meta:
        verbose_name = "Подписка"
        verbose_name_plural = "Подписки"
        constraints: ClassVar[tuple] = (
            UniqueConstraint(
                fields=("user", "author"),
                name="unique_user_author",
            ),
            CheckConstraint(
                check=~Q(user=F("author")),
                name="prevent_self_follow",
            ),
        )

    def __str__(self):
        return f"{self.user.username} подписан на {self.author.username}"
