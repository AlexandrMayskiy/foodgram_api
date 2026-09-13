from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import (
    SAFE_METHODS,
    AllowAny,
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.response import Response

from .filters import RecipeFilter
from .models import (
    Favorite,
    Ingredient,
    Recipe,
    RecipeIngredient,
    ShoppingCart,
    Tag,
)
from .pagination import CustomPagination
from .serializers import (
    IngredientSerializer,
    RecipeReadSerializer,
    RecipeShortSerializer,
    RecipeWriteSerializer,
    TagSerializer,
)


class IngredientSearchFilter(filters.SearchFilter):
    """Кастомный фильтр поиска ингредиентов по названию."""

    search_param = "name"


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    """Вьюсет для просмотра тегов."""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (AllowAny,)
    pagination_class = None


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    """Вьюсет для просмотра ингредиентов с поиском по названию."""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = (AllowAny,)
    pagination_class = None
    filter_backends = (IngredientSearchFilter,)
    search_fields = ("^name", "name")


class RecipeViewSet(viewsets.ModelViewSet):
    """Вьюсет для работы с рецептами."""

    queryset = Recipe.objects.all()
    permission_classes = (IsAuthenticatedOrReadOnly,)
    pagination_class = CustomPagination
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter

    def get_serializer_class(self):
        if self.request.method in SAFE_METHODS:
            return RecipeReadSerializer
        return RecipeWriteSerializer

    def create(self, request, *args, **kwargs):
        """Создание рецепта через сериализатор записи."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    @action(
        detail=True,
        methods=["post", "delete"],
        permission_classes=[IsAuthenticated],
    )
    def favorite(self, request, pk=None):
        """Добавить рецепт в избранное или удалить из него."""
        return self._add_or_delete_relation(request, pk, Favorite, "избранное")

    @action(
        detail=True,
        methods=["post", "delete"],
        permission_classes=[IsAuthenticated],
    )
    def shopping_cart(self, request, pk=None):
        """Добавить рецепт в список покупок или удалить из него."""
        return self._add_or_delete_relation(
            request, pk, ShoppingCart, "список покупок"
        )

    @action(
        detail=False, methods=["get"], permission_classes=[IsAuthenticated]
    )
    def download_shopping_cart(self, request):
        """Агрегирует ингредиенты из корзины и выгружает TXT-файл."""
        user = request.user

        ingredients = (
            RecipeIngredient.objects.filter(recipe__shopping_cart__user=user)
            .values("ingredient__name", "ingredient__measurement_unit")
            .annotate(total_amount=Sum("amount"))
            .order_by("ingredient__name")
        )

        if not ingredients.exists():
            return Response(
                {"errors": "Ваш список покупок пуст!"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        shopping_list = [
            (
                f"Список покупок для пользователя "
                f"{user.get_full_name() or user.username}:\n\n"
            )
        ]
        for item in ingredients:
            shopping_list.append(
                f"- {item['ingredient__name']} "
                f"({item['ingredient__measurement_unit']}) "
                f"— {item['total_amount']}\n"
            )

        response = Response(
            "".join(shopping_list), content_type="text/plain; charset=utf-8"
        )
        response["Content-Disposition"] = (
            'attachment; filename="shopping_list.txt"'
        )
        return response

    def _add_or_delete_relation(self, request, pk, model, name_for_error):
        """Вспомогательный метод для обработки связей (Избранное / Корзина)."""
        user = request.user
        recipe = get_object_or_404(Recipe, id=pk)
        relation = model.objects.filter(user=user, recipe=recipe)

        if request.method == "POST":
            if relation.exists():
                return Response(
                    {"errors": f"Рецепт уже добавлен в {name_for_error}!"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            model.objects.create(user=user, recipe=recipe)
            serializer = RecipeShortSerializer(recipe)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if request.method == "DELETE":
            if relation.exists():
                relation.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response(
                {"errors": f"Рецепта нет в вашем {name_for_error}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, url_path='get-link')
    def get_link(self, request, pk=None):
        """Возвращает короткую ссылку на рецепт."""
        recipe = self.get_object()
        short_link = request.build_absolute_uri(f'/s/{recipe.id}/')
        return Response({'short-link': short_link}, status=status.HTTP_200_OK)


def short_link_redirect(request, pk):
    """Перенаправляет с ссылки на полную страницу рецепта."""
    recipe = get_object_or_404(Recipe, pk=pk)
    return redirect(f'/recipes/{recipe.id}/')
