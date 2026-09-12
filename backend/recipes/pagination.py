from rest_framework.pagination import PageNumberPagination


class CustomPagination(PageNumberPagination):
    """Пагинатор с настраиваемым размером страницы через параметр limit."""

    page_size_query_param = "limit"
    page_size = 6
    max_page_size = 50
