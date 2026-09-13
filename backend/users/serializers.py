import base64

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from djoser.serializers import UserCreateSerializer, UserSerializer
from rest_framework import serializers

from .models import Follow

User = get_user_model()


class Base64ImageField(serializers.ImageField):
    """Кастомное поле для обработки аватарки в формате Base64."""

    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith("data:image"):
            img_format, imgstr = data.split(";base64,")
            ext = img_format.split("/")[-1]
            data = ContentFile(base64.b64decode(imgstr), name=f"avatar.{ext}")
        return super().to_internal_value(data)


class CustomUserCreateSerializer(UserCreateSerializer):
    """Сериализатор для регистрации нового пользователя."""

    class Meta:
        model = User
        fields = (
            "email",
            "id",
            "username",
            "first_name",
            "last_name",
            "password",
        )


class CustomUserSerializer(UserSerializer):
    """Сериализатор для вывода информации о пользователе."""

    is_subscribed = serializers.SerializerMethodField()
    avatar = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = (
            "email",
            "id",
            "username",
            "first_name",
            "last_name",
            "is_subscribed",
            "avatar",
        )
        read_only_fields = (
            "email",
            "id",
            "username",
            "first_name",
            "last_name",
        )

    def get_is_subscribed(self, obj):
        request = self.context.get("request")
        if request is None or request.user.is_anonymous or request.user == obj:
            return False
        return Follow.objects.filter(user=request.user, author=obj).exists()


class FollowSerializer(serializers.ModelSerializer):
    """Сериализатор для вывода авторов, на которых подписан пользователь."""

    is_subscribed = serializers.SerializerMethodField()
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "email",
            "id",
            "username",
            "first_name",
            "last_name",
            "is_subscribed",
            "recipes",
            "recipes_count",
        )

    def get_is_subscribed(self, obj):
        return True

    def get_recipes(self, obj):
        from recipes.serializers import RecipeShortSerializer

        request = self.context.get("request")
        limit = request.query_params.get("recipes_limit") if request else None
        recipes = obj.recipes.all()

        if limit:
            try:
                recipes = recipes[: int(limit)]
            except ValueError:
                pass
        return RecipeShortSerializer(
            recipes, many=True, context=self.context
        ).data

    def get_recipes_count(self, obj):
        return obj.recipes.count()
