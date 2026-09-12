from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models

User = get_user_model()


class Tag(models.Model):
    """Модель тега (Завтрак, Обед и т.д.)."""

    name = models.CharField("Название тега", max_length=200, unique=True)
    color = models.CharField("Цвет в HEX", max_length=7, unique=True)
    slug = models.SlugField("Уникальный слаг", max_length=200, unique=True)

    class Meta:
        verbose_name = "Тег"
        verbose_name_plural = "Теги"
        ordering = ("name",)

    def __str__(self):
        return self.name


class Ingredient(models.Model):
    """Модель ингредиента (Картофель, Сахар)."""

    name = models.CharField("Название ингредиента", max_length=200)
    measurement_unit = models.CharField("Единица измерения", max_length=200)

    class Meta:
        verbose_name = "Ингредиент"
        verbose_name_plural = "Ингредиенты"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["name", "measurement_unit"],
                name="unique_ingredient_unit",
            )
        ]

    def __str__(self):
        return f"{self.name}, {self.measurement_unit}"


class Recipe(models.Model):
    """Модель рецепта."""

    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="recipes",
        verbose_name="Автор рецепта",
    )
    name = models.CharField("Название рецепта", max_length=200)
    image = models.ImageField(
        "Ссылка на картинку",
        upload_to="recipes/images/",
    )
    text = models.TextField("Описание рецепта")
    ingredients = models.ManyToManyField(
        Ingredient,
        through="RecipeIngredient",
        related_name="recipes",
        verbose_name="Список ингредиентов",
    )
    tags = models.ManyToManyField(
        Tag, related_name="recipes", verbose_name="Список тегов"
    )
    cooking_time = models.PositiveSmallIntegerField(
        "Время приготовления (в минутах)",
        validators=[
            MinValueValidator(
                1, message="Время приготовления должно быть не менее 1 минуты!"
            )
        ],
    )
    pub_date = models.DateTimeField("Дата публикации", auto_now_add=True)

    class Meta:
        verbose_name = "Рецепт"
        verbose_name_plural = "Рецепты"
        ordering = ("-pub_date",)

    def __str__(self):
        return self.name


class RecipeIngredient(models.Model):
    """Связующая модель для ингредиентов и рецептов с указанием количества."""

    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name="recipe_ingredients",
        verbose_name="Рецепт",
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        related_name="ingredient_recipes",
        verbose_name="Ингредиент",
    )
    amount = models.PositiveSmallIntegerField(
        "Количество",
        validators=[
            MinValueValidator(1, message="Количество должно быть не менее 1!")
        ],
    )

    class Meta:
        verbose_name = "Ингредиент в рецепте"
        verbose_name_plural = "Ингредиенты в рецепте"
        constraints = [
            models.UniqueConstraint(
                fields=["recipe", "ingredient"],
                name="unique_recipe_ingredient"
            )
        ]

    def __str__(self):
        return (
            f"{self.ingredient.name} — {self.amount} "
            f"({self.ingredient.measurement_unit})"
        )


class FavoriteAndCartBase(models.Model):
    """Абстрактная базовая модель для Избранного и Списка покупок."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name="Пользователь"
    )
    recipe = models.ForeignKey(
        Recipe, on_delete=models.CASCADE, verbose_name="Рецепт"
    )

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.user.username} -> {self.recipe.name}"


class Favorite(FavoriteAndCartBase):
    """Модель Избранного."""

    class Meta:
        verbose_name = "Избранное"
        verbose_name_plural = "Избранное"
        default_related_name = "favorites"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "recipe"], name="unique_favorite_recipe"
            )
        ]


class ShoppingCart(FavoriteAndCartBase):
    """Модель Списка покупок (корзины)."""

    class Meta:
        verbose_name = "Список покупок"
        verbose_name_plural = "Список покупок"
        default_related_name = "shopping_cart"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "recipe"], name="unique_shopping_cart_recipe"
            )
        ]
