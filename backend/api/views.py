from django.contrib.auth import get_user_model
from django.db.models import F, Sum
from django.http import FileResponse
from django.urls import reverse
from django_filters.rest_framework import DjangoFilterBackend
from django.http import Http404
from djoser.views import UserViewSet as DjoserUserViewSet
from recipes.models import (
    Favorite,
    Ingredient,
    Recipe,
    RecipeIngredient,
    ShoppingCart,
    Tag,
)
from rest_framework import status, viewsets
from rest_framework.decorators import action, renderer_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import (
    SAFE_METHODS,
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.renderers import BaseRenderer
from rest_framework.response import Response
from users.models import Follow

from api.filters import RecipeFilter, IngredientSearchFilter
from api.pagination import Pagination
from api.serializers import (
    FollowSerializer,
    IngredientSerializer,
    RecipeReadSerializer,
    RecipeShortSerializer,
    RecipeWriteSerializer,
    TagSerializer,
    UserSerializer,
    RecipeRelationSerializer,
)

User = get_user_model()


class UserViewSet(DjoserUserViewSet):
    """Кастомный ViewSet для пользователей, подписок и аватаров."""

    queryset = User.objects.all()
    serializer_class = UserSerializer
    pagination_class = Pagination

    def get_serializer_class(self):
        """Динамическая подмена сериализатора для действий подписок."""
        if self.action in ("subscriptions", "subscribe"):
            return FollowSerializer
        return super().get_serializer_class()

    @action(
        detail=False,
        permission_classes=(IsAuthenticated,),
        url_path="subscriptions"
    )
    def subscriptions(self, request):
        """Возвращает авторов, на которых подписан пользователь."""
        user = request.user
        authors = User.objects.filter(following__user=user)

        paginated_queryset = self.paginate_queryset(authors)
        serializer = self.get_serializer(paginated_queryset, many=True)
        return self.get_paginated_response(serializer.data)

    @action(
        detail=True,
        methods=("post",),
        permission_classes=(IsAuthenticated,),
        url_path="subscribe",
    )
    def subscribe(self, request, id=None):
        """Создать подписку."""
        author = self.get_object()
        context = self.get_serializer_context()
        context["author"] = author
        serializer = self.get_serializer(data=request.data, context=context)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            self.get_serializer(author).data,
            status=status.HTTP_201_CREATED
        )

    @subscribe.mapping.delete
    def delete_subscribe(self, request, id=None):
        """Удалить подписку без лишних запросов к БД."""
        user = request.user
        author = self.get_object()
        deleted_count, _ = Follow.objects.filter(
            user=user, author=author
        ).delete()
        if not deleted_count:
            raise Http404("Вы не подписаны на этого автора.")
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
            serializer = self.get_serializer(user, data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response({"avatar": user.avatar.url})

        if request.method == "DELETE":
            if user.avatar:
                user.avatar.delete()
                user.save()
            return Response(status=status.HTTP_204_NO_CONTENT)


class BaseReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    """Базовый вьюсет для тегов и ингредиентов с отключенной пагинацией."""

    pagination_class = None


class TagViewSet(BaseReadOnlyViewSet):
    """Вьюсет для просмотра тегов."""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer


class IngredientViewSet(BaseReadOnlyViewSet):
    """Вьюсет для просмотра ингредиентов с поиском по названию."""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    filter_backends = (IngredientSearchFilter,)
    search_fields = ("^name",)


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
        methods=("post",),
        permission_classes=(IsAuthenticated,),
    )
    def favorite(self, request, pk=None):
        """Добавить рецепт в избранное."""
        recipe = self.get_object()
        context = self.get_serializer_context()
        context.update({"recipe": recipe, "model": Favorite})

        serializer = RecipeRelationSerializer(
            data=request.data,
            context=context
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            RecipeShortSerializer(recipe, context={"request": request}).data,
            status=status.HTTP_201_CREATED
        )

    @favorite.mapping.delete
    def delete_favorite(self, request, pk=None):
        """Удалить рецепт из избранного."""
        recipe = self.get_object()
        deleted_count, _ = Favorite.objects.filter(
            user=request.user, recipe=recipe
        ).delete()
        if not deleted_count:
            raise ValidationError("Рецепта нет в списке избранного.")
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=("post",),
        permission_classes=(IsAuthenticated,),
    )
    def shopping_cart(self, request, pk=None):
        """Добавить рецепт в список покупок."""
        recipe = self.get_object()
        context = self.get_serializer_context()
        context.update({"recipe": recipe, "model": ShoppingCart})

        serializer = RecipeRelationSerializer(
            data=request.data,
            context=context
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            RecipeShortSerializer(recipe, context={"request": request}).data,
            status=status.HTTP_201_CREATED
        )

    @shopping_cart.mapping.delete
    def delete_shopping_cart(self, request, pk=None):
        """Удалить рецепт из списка покупок."""
        recipe = self.get_object()
        deleted_count, _ = ShoppingCart.objects.filter(
            user=request.user, recipe=recipe
        ).delete()
        if not deleted_count:
            raise ValidationError("Рецепта нет в корзине покупок.")
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        permission_classes=(IsAuthenticated,),
    )
    @renderer_classes((BaseRenderer,))
    def download_shopping_cart(self, request):
        """Агрегирует ингредиенты из корзины и выгружает TXT-файл."""
        user = request.user

        ingredients = (
            RecipeIngredient.objects.filter(recipe__shopping_cart__user=user)
            .values(
                name=F("ingredient__name"),
                unit=F("ingredient__measurement_unit")
            )
            .annotate(total_amount=Sum("amount"))
            .order_by("name")
        )

        if not ingredients.exists():
            raise ValidationError("Ваш список покупок пуст!")

        shopping_list = (
            f"- {item.get('name')} ({item.get('unit')}) "
            f"— {item.get('total_amount')}\n"
            for item in ingredients
        )

        username = user.get_full_name() or user.username
        header = f"Список покупок для пользователя {username}:\n\n"

        file_content = f"{header}{''.join(shopping_list)}"

        response = FileResponse(
            file_content,
            content_type="text/plain; charset=utf-8",
            as_attachment=True,
            filename="shopping_list.txt"
        )
        return response

    @action(detail=True, methods=("get",), url_path="get-link")
    def get_link(self, request, pk=None):
        """Возвращает короткую ссылку на рецепт."""
        recipe = self.get_object()
        short_path = reverse("short_link", kwargs={"pk": recipe.id})
        short_link = request.build_absolute_uri(short_path)
        return Response({"short-link": short_link})
