from django.conf import settings
from django.shortcuts import get_object_or_404, redirect

from .models import Recipe


def short_link_redirect(request, pk):
    """Перенаправляет с короткой ссылки на полную страницу рецепта."""
    recipe = get_object_or_404(Recipe, pk=pk)

    return redirect(settings.RECIPE_FRONTEND_URL.format(recipe.id))
