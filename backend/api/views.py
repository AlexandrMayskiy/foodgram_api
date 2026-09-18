from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.http import HttpResponse
from django.urls import reverse
from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet as DjoserUserViewSet
from recipes.models import (
    Favorite,
    Ingredient,
    Recipe,
    RecipeIngredient,
    ShoppingCart,
    Tag,
)
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import (
    SAFE_METHODS,
    AllowAny,
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.response import Response
from users.models import Follow

from api.filters import RecipeFilter
from api.pagination import Pagination
from api.serializers import (
    FollowSerializer,
    IngredientSerializer,
    RecipeReadSerializer,
    RecipeShortSerializer,
    RecipeWriteSerializer,
    TagSerializer,
    UserSerializer,
)

User = get_user_model()


class CustomUserViewSet(DjoserUserViewSet):
    """Кастомный ViewSet для пользователей, включая подписки и аватары."""

    queryset = User.objects.all()
    serializer_class = UserSerializer
    pagination_class = Pagination

    @action(
        detail=False, permission_classes=(IsAuthenticated,), url_path="subscriptions"
    )
    def subscriptions(self, request):
        """Возвращает авторов, на которых подписан пользователь."""

        user = request.user
        authors = User.objects.filter(following__user=user)

        paginated_queryset = self.paginate_queryset(authors)
        serializer = FollowSerializer(
            paginated_queryset, many=True, context={"request": request}
        )
        return self.get_paginated_response(serializer.data)

    @action(
        detail=True,
        methods=("post", "delete"),
        permission_classes=(IsAuthenticated,),
        url_path="subscribe",
    )
    def subscribe(self, request, id=None):
        """Создать подписку или удалить её."""

        user = request.user
        author = self.get_object()
        subscription = Follow.objects.filter(user=user, author=author)

        if request.method == "POST":
            if user == author:
                raise ValidationError("Вы не можете подписаться на себя!")
            if subscription.exists():
                raise ValidationError("Вы уже подписаны на этого автора!")

            Follow.objects.create(user=user, author=author)
            serializer = FollowSerializer(author, context={"request": request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if request.method == "DELETE":
            if not subscription.exists():
                raise ValidationError("Вы не подписаны на этого автора.")
            subscription.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        methods=("put", "delete"),
        permission_classes=(IsAuthenticated,),
        url_path="me/avatar",
    )
    def avatar(self, request):
        """Управление аватаром текущего пользователя."""

        user = request.user

        if request.method == "PUT":
            if "avatar" not in request.data:
                raise ValidationError("Поле avatar обязательно!")
            serializer = UserSerializer(
                user,
                data=request.data,
                partial=True,
                context={"request": request},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response({"avatar": user.avatar.url}, status=status.HTTP_200_OK)

        if request.method == "DELETE":
            if user.avatar:
                user.avatar.delete()
                user.save()
            return Response(status=status.HTTP_204_NO_CONTENT)


class IngredientSearchFilter(filters.SearchFilter):
    """Кастомный фильм поиска ингредиентов по названию."""

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
    pagination_class = Pagination
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter

    def get_serializer_class(self):
        if self.request.method in SAFE_METHODS:
            return RecipeReadSerializer
        return RecipeWriteSerializer

    @action(
        detail=True,
        methods=("post", "delete"),
        permission_classes=(IsAuthenticated,),
    )
    def favorite(self, request, pk=None):
        """Добавить рецепт в избранное или удалить из него."""

        return self._add_or_delete_relation(request, pk, Favorite)

    @action(
        detail=True,
        methods=("post", "delete"),
        permission_classes=(IsAuthenticated,),
    )
    def shopping_cart(self, request, pk=None):
        """Добавить рецепт в список покупок или удалить из него."""

        return self._add_or_delete_relation(request, pk, ShoppingCart)

    @action(
        detail=False,
        methods=("get",),
        permission_classes=(IsAuthenticated,),
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
            raise ValidationError("Ваш список покупок пуст!")

        shopping_list = (
            f"- {item['ingredient__name']} "
            f"({item['ingredient__measurement_unit']}) "
            f"— {item['total_amount']}\n"
            for item in ingredients
        )

        header = (
            f"Список покупок для пользователя "
            f"{user.get_full_name() or user.username}:\n\n"
        )
        file_content = header + "".join(shopping_list)
        response = HttpResponse(file_content, content_type="text/plain; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="shopping_list.txt"'
        return response

    def _add_or_delete_relation(self, request, pk, model):
        """Вспомогательный метод для обработки связей (Избранное / Корзина)."""

        user = request.user
        recipe = self.get_object()
        relation = model.objects.filter(user=user, recipe=recipe)

        if request.method == "POST":
            if relation.exists():
                raise ValidationError("Рецепт уже добавлен!")

            model.objects.create(user=user, recipe=recipe)
            serializer = RecipeShortSerializer(recipe, context={"request": request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if request.method == "DELETE":
            if not relation.exists():
                raise ValidationError("Рецепта нет в списке.")
            relation.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=("get",), url_path="get-link")
    def get_link(self, request, pk=None):
        """Возвращает короткую ссылку на рецепт."""

        recipe = self.get_object()
        short_path = reverse("short_link", kwargs={"pk": recipe.id})
        short_link = request.build_absolute_uri(short_path)
        return Response({"short-link": short_link}, status=status.HTTP_200_OK)
