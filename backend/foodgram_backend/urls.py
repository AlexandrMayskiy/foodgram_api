from django.contrib import admin
from django.urls import include, path, re_path
from recipes.views import short_link_redirect

urlpatterns = [
    path("admin/", admin.site.urls),
    re_path(r"^s/(?P<pk>\d+)/?$", short_link_redirect, name="short_link"),
    path("api/", include("api.urls", namespace="api")),
]
