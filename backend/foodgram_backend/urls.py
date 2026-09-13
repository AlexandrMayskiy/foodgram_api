from django.contrib import admin
from django.urls import include, path
from users.views import (
    subscribe_action,
    subscriptions_list,
    user_avatar_action,
)
from recipes.views import short_link_redirect

urlpatterns = [
    path("admin/", admin.site.urls),
    path("s/<int:pk>/", short_link_redirect, name="short_link"),
    path("api/users/subscriptions/", subscriptions_list, name="subscriptions"),
    path(
        "api/users/<int:user_id>/subscribe/",
        subscribe_action,
        name="subscribe",
    ),
    path("api/users/me/avatar/", user_avatar_action, name="user_avatar"),
    path("api/", include("djoser.urls")),
    path("api/auth/", include("djoser.urls.authtoken")),
    path("api/", include("recipes.urls")),
]
