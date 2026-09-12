from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from recipes.pagination import CustomPagination
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Follow
from .serializers import CustomUserSerializer, FollowSerializer

User = get_user_model()


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def subscriptions_list(request):
    """Возвращает авторов, на которых подписан пользователь, с пагинацией."""
    user = request.user
    authors = User.objects.filter(following__user=user)

    paginator = CustomPagination()
    result_page = paginator.paginate_queryset(authors, request)

    serializer = FollowSerializer(result_page, many=True, context={"request": request})
    return paginator.get_paginated_response(serializer.data)


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def subscribe_action(request, user_id):
    """Создать подписку или удалить её."""
    user = request.user
    author = get_object_or_404(User, id=user_id)
    relation = Follow.objects.filter(user=user, author=author)

    if request.method == "POST":
        if user == author:
            return Response(
                {"errors": "Вы не можете подписаться на самого себя!"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if relation.exists():
            return Response(
                {"errors": "Вы уже подписаны на этого автора!"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        Follow.objects.create(user=user, author=author)
        serializer = FollowSerializer(author, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    if request.method == "DELETE":
        if relation.exists():
            relation.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(
            {"errors": "Вы не подписаны на этого автора."},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def user_avatar_action(request):
    """Управление аватаром текущего пользователя."""
    user = request.user

    if request.method == "PUT":
        if "avatar" not in request.data:
            return Response(
                {"errors": "Поле avatar обязательно!"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = CustomUserSerializer(
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
