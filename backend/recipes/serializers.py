import base64

from django.core.files.base import ContentFile
from rest_framework import serializers

from .models import (
    Favorite,
    Ingredient,
    Recipe,
    RecipeIngredient,
    ShoppingCart,
    Tag,
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
    measurement_unit = serializers.ReadOnlyField(source="ingredient.measurement_unit")

    class Meta:
        model = RecipeIngredient
        fields = ("id", "name", "measurement_unit", "amount")


class RecipeReadSerializer(serializers.ModelSerializer):
    """Сериализатор для безопасного чтения рецептов (GET)."""

    tags = TagSerializer(many=True, read_only=True)
    author = serializers.SerializerMethodField()
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

    def get_author(self, obj):
        from users.serializers import CustomUserSerializer

        return CustomUserSerializer(obj.author, context=self.context).data

    def get_is_favorited(self, obj):
        request = self.context.get("request")
        if request is None or request.user.is_anonymous:
            return False
        return Favorite.objects.filter(user=request.user, recipe=obj).exists()

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get("request")
        if request is None or request.user.is_anonymous:
            return False
        return ShoppingCart.objects.filter(user=request.user, recipe=obj).exists()


class Base64ImageField(serializers.ImageField):
    """Кастомное поле для обработки картинок, закодированных в Base64."""

    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith("data:image"):
            img_format, imgstr = data.split(";base64,")
            ext = img_format.split("/")[-1]
            data = ContentFile(base64.b64decode(imgstr), name=f"temp.{ext}")
        return super().to_internal_value(data)


class RecipeIngredientWriteSerializer(serializers.Serializer):
    """Вспомогательный сериализатор для добавления ингредиентов при записи."""

    id = serializers.IntegerField()
    amount = serializers.IntegerField()


class RecipeWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления рецептов (POST, PATCH)."""

    tags = serializers.PrimaryKeyRelatedField(queryset=Tag.objects.all(), many=True)
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

        ingredient_ids = [item["id"] for item in value]
        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError(
                "Ингредиенты в рецепте не должны повторяться!"
            )

        for item in value:
            if int(item["amount"]) < 1:
                raise serializers.ValidationError(
                    "Количество ингредиента должно быть больше 0!"
                )
        return value

    def validate_tags(self, value):
        if not value:
            raise serializers.ValidationError("Необходимо выбрать хотя бы один тег!")
        return value

    def save_ingredients(self, recipe, ingredients_data):
        """Вспомогательный метод для безопасного сохранения ингредиентов."""
        RecipeIngredient.objects.filter(recipe=recipe).delete()

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
