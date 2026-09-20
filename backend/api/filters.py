from django_filters import rest_framework as django_filters
from rest_framework import filters as rest_filters

from recipes.models import Recipe, Tag


class RecipeFilter(django_filters.FilterSet):
    """Фильтр для рецептов по тегам, автору, избранному и корзине."""

    tags = django_filters.ModelMultipleChoiceFilter(
        field_name="tags__slug",
        to_field_name="slug",
        queryset=Tag.objects.all(),
    )
    is_favorited = django_filters.BooleanFilter(method="filter_is_favorited")
    is_in_shopping_cart = django_filters.BooleanFilter(
        method="filter_is_in_shopping_cart"
    )

    class Meta:
        model = Recipe
        fields = ("tags", "author", "is_favorited", "is_in_shopping_cart")

    def filter_is_favorited(self, queryset, name, value):
        user = self.request.user
        if value and user.is_authenticated:
            return queryset.filter(favorites__user=user)
        return queryset

    def filter_is_in_shopping_cart(self, queryset, name, value):
        user = self.request.user
        if value and user.is_authenticated:
            return queryset.filter(shopping_cart__user=user)
        return queryset


class IngredientSearchFilter(rest_filters.SearchFilter):
    """Кастомный фильтр поиска ингредиентов по названию."""

    search_param = "name"
