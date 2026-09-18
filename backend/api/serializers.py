import base64

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.validators import MaxValueValidator, MinValueValidator
from djoser.serializers import UserSerializer as DjoserUserSerializer
from recipes.models import (
    Favorite,
    Ingredient,
    Recipe,
    RecipeIngredient,
    ShoppingCart,
    Tag,
)
from rest_framework import serializers
from users.models import Follow

User = get_user_model()


class Base64ImageField(serializers.ImageField):
    """Кастомное поле для обработки картинок и аватарок в формате Base64."""

    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith("data:image"):
            img_format, imgstr = data.split(";base64,")
            ext = img_format.split("/")[-1]
            data = ContentFile(base64.b64decode(imgstr), name=f"temp.{ext}")
        return super().to_internal_value(data)


class UserSerializer(DjoserUserSerializer):
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
        """Проверяет подписку текущего пользователя на автора."""
        request = self.context.get("request")
        user = request.user if request else None
        return bool(
            user
            and user.is_authenticated
            and user.id != obj.id
            and obj.following.filter(user_id=user.id).exists()
        )


class TagSerializer(serializers.ModelSerializer):
    """Сериализатор для вывода тегов."""

    class Meta:
        model = Tag
        fields = ("id", "name", "color", "slug")


class IngredientSerializer(serializers.ModelSerializer):
    """Сериализатор для вывода ингредиентов."""

    class Meta:
        model = Ingredient
        fields = ("id", "name", "measurement_unit")


class RecipeIngredientReadSerializer(serializers.ModelSerializer):
    """Сериализатор для вывода ингредиентов с количеством в рецепте."""

    id = serializers.ReadOnlyField(source="ingredient.id")
    name = serializers.ReadOnlyField(source="ingredient.name")
    measurement_unit = serializers.ReadOnlyField(
        source="ingredient.measurement_unit",
    )

    class Meta:
        model = RecipeIngredient
        fields = ("id", "name", "measurement_unit", "amount")


class RecipeReadSerializer(serializers.ModelSerializer):
    """Сериализатор для безопасного чтения рецептов (GET)."""

    tags = TagSerializer(many=True, read_only=True)
    author = UserSerializer(read_only=True)
    ingredients = RecipeIngredientReadSerializer(
        source="recipe_ingredients", many=True, read_only=True
    )
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            "id",
            "tags",
            "author",
            "ingredients",
            "is_favorited",
            "is_in_shopping_cart",
            "name",
            "image",
            "text",
            "cooking_time",
        )

    def get_is_favorited(self, obj):
        request = self.context.get("request")
        if request is None or request.user.is_anonymous:
            return False
        return Favorite.objects.filter(user=request.user, recipe=obj).exists()

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get("request")
        if request is None or request.user.is_anonymous:
            return False
        return ShoppingCart.objects.filter(
            user=request.user, recipe=obj
        ).exists()


class RecipeIngredientWriteSerializer(serializers.Serializer):
    """Вспомогательный сериализатор для добавления ингредиентов при записи."""

    id = serializers.IntegerField()
    amount = serializers.IntegerField(
        validators=(
            MinValueValidator(
                1,
                message="Количество должно быть не менее 1!",
            ),
            MaxValueValidator(
                10000,
                message="Количество слишком велико!",
            ),
        )
    )


class RecipeWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления рецептов (POST, PATCH)."""

    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True
    )
    ingredients = RecipeIngredientWriteSerializer(many=True)
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = (
            "tags",
            "ingredients",
            "name",
            "image",
            "text",
            "cooking_time",
        )

    def validate_ingredients(self, value):
        if not value:
            raise serializers.ValidationError(
                "Необходимо выбрать хотя бы один ингредиент!"
            )

        ingredient_ids = [ingredient["id"] for ingredient in value]
        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError(
                "Ингредиенты в рецепте не должны повторяться!"
            )
        return value

    def validate_tags(self, value):
        if not value:
            raise serializers.ValidationError(
                "Необходимо выбрать хотя бы один тег!"
            )
        return value

    def save_ingredients(self, recipe, ingredients_data):
        """Вспомогательный метод для безопасного сохранения ингредиентов."""

        recipe.recipe_ingredients.all().delete()

        db_ingredients = []
        for ingredient in ingredients_data:
            ing_id = ingredient.get("id")
            if hasattr(ing_id, "id"):
                ing_id = ing_id.id

            db_ingredients.append(
                RecipeIngredient(
                    recipe=recipe,
                    ingredient_id=int(ing_id),
                    amount=int(ingredient.get("amount")),
                )
            )

        RecipeIngredient.objects.bulk_create(db_ingredients)

    def create(self, validated_data):
        tags = validated_data.pop("tags")
        ingredients_data = validated_data.pop("ingredients")

        author = self.context.get("request").user
        recipe = Recipe.objects.create(author=author, **validated_data)

        recipe.tags.set(tags)
        self.save_ingredients(recipe, ingredients_data)
        return recipe

    def update(self, instance, validated_data):
        tags = validated_data.pop("tags", None)
        ingredients_data = validated_data.pop("ingredients", None)

        instance = super().update(instance, validated_data)

        if tags is not None:
            instance.tags.set(tags)
        if ingredients_data is not None:
            self.save_ingredients(instance, ingredients_data)

        return instance

    def to_representation(self, instance):
        """Возвращает структуру сериализатора для чтения после записи."""

        context = {"request": self.context.get("request")}
        return RecipeReadSerializer(instance, context=context).data


class RecipeShortSerializer(serializers.ModelSerializer):
    """Краткий сериализатор рецепта для списков Избранного и Корзины."""

    class Meta:
        model = Recipe
        fields = ("id", "name", "image", "cooking_time")


class FollowSerializer(UserSerializer):
    """Сериализатор для вывода авторов, на которых подписан пользователь."""

    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + (
            "recipes",
            "recipes_count",
        )

    def validate(self, data):
        """Дополнительные проверки уникальности подписок."""

        request = self.context.get("request")
        user = request.user
        author = self.context.get("author")

        if user == author:
            raise serializers.ValidationError(
                "Нельзя подписаться на самого себя!"
            )
        if Follow.objects.filter(user=user, author=author).exists():
            raise serializers.ValidationError(
                "Вы уже подписаны на этого автора!"
            )
        return data

    def get_recipes(self, obj):
        request = self.context.get("request")
        limit = request.query_params.get("recipes_limit") if request else None
        recipes = obj.recipes.all()

        if limit and limit.isdigit():
            recipes = recipes[: int(limit)]

        return RecipeShortSerializer(
            recipes, many=True, context=self.context
        ).data

    def get_recipes_count(self, obj):
        return obj.recipes.count()
