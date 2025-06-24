from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.http import int_to_base36, base36_to_int
from rest_framework import viewsets, status, permissions, serializers, mixins, pagination
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly, AllowAny
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Prefetch, Exists, OuterRef
from django.http import HttpResponse, HttpResponseRedirect
from rest_framework.views import APIView

from .filters import IngredientFilter, RecipeFilter
from djoser.views import UserViewSet as DjoserUserViewSet
from .serializers import (
    IngredientSerializer,
    RecipeSerializer, RecipeCreateUpdateSerializer,
    UserSerializer, SetPasswordSerializer, SetAvatarSerializer, ShortLinkSerializer
)
from recipes.models import Ingredient, Recipe, Favorite, ShoppingCart, RecipeIngredient
from users.models import Subscription


User = get_user_model()


class UserViewSet(DjoserUserViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    @action(['post'], detail=False, permission_classes=[permissions.IsAuthenticated])
    def set_password(self, request):
        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.data['current_password']):
            return Response(
                {'current_password': ['Неверный пароль']},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(serializer.data['new_password'])
        user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['put', 'delete'],
            permission_classes=[permissions.IsAuthenticated],
            url_path='me/avatar',
            url_name='avatar_action')
    def handle_avatar(self, request):
        user = request.user

        # Обработка PUT запроса (установка аватара)
        if request.method == 'PUT':
            serializer = SetAvatarSerializer(
                user,
                data=request.data,
                context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(
                {"avatar": UserSerializer(user, context={'request': request}).data['avatar']},
                status=status.HTTP_200_OK
            )

        # Обработка DELETE запроса (удаление аватара)
        elif request.method == 'DELETE':
            if user.avatar and user.avatar.name != 'users/avatars/default.png':
                user.avatar.delete(save=False)

            # Устанавливаем аватар по умолчанию
            user.avatar = ''
            user.save(update_fields=['avatar'])
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(['get'], detail=False, permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(['post'], detail=True, permission_classes=[permissions.IsAuthenticated])
    def subscribe(self, request, id=None):
        author = get_object_or_404(User, id=id)
        if request.user == author:
            return Response(
                {'error': 'Нельзя подписаться на самого себя'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if request.user.following.filter(author=author).exists():
            return Response(
                {'error': 'Вы уже подписаны на этого автора'},
                status=status.HTTP_400_BAD_REQUEST
            )

        Subscription.objects.create(user=request.user, author=author)

        recipes_limit = request.query_params.get('recipes_limit')
        serializer = UserWithRecipesSerializer(
            author,
            context={
                'request': request,
                'recipes_limit': recipes_limit
            }
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @subscribe.mapping.delete
    def unsubscribe(self, request, id=None):
        author = get_object_or_404(User, id=id)
        subscription = request.user.following.filter(author=author)

        if not subscription.exists():
            return Response(
                {'error': 'Вы не подписаны на этого автора'},
                status=status.HTTP_400_BAD_REQUEST
            )

        subscription.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(['get'], detail=False, permission_classes=[permissions.IsAuthenticated])
    def subscriptions(self, request):
        # Получаем авторов, на которых подписан пользователь
        authors = User.objects.filter(followers__user=request.user)

        # Пагинация
        # Используем встроенную пагинацию Django REST Framework
        paginator = pagination.LimitOffsetPagination()
        paginator.default_limit = 6  # Значение по умолчанию из настроек

        result_page = paginator.paginate_queryset(authors, request)
        recipes_limit = request.query_params.get('recipes_limit')

        # Сериализация с ограничением рецептов
        serializer = UserWithRecipesSerializer(
            result_page,
            many=True,
            context={
                'request': request,
                'recipes_limit': recipes_limit,
                'is_subscriptions_list': True
            }
        )
        return paginator.get_paginated_response(serializer.data)


class UserWithRecipesSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'email', 'id', 'username', 'first_name',
            'last_name', 'is_subscribed', 'recipes',
            'recipes_count', 'avatar'
        )

    def get_avatar(self, obj):
        # Используем ту же логику, что и в UserSerializer
        if obj.avatar:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.avatar.url) if request else obj.avatar.url
        return None

    # def get_is_subscribed(self, obj):
    #     request = self.context.get('request')
    #     if request and request.user.is_authenticated:
    #         return Subscription.objects.filter(
    #             user=request.user,
    #             author=obj
    #         ).exists()
    #     return False

    def get_is_subscribed(self, obj):
        # Всегда True, так как это подписки текущего пользователя
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False

        if self.context.get('is_subscriptions_list'):
            return True

        return Subscription.objects.filter(
            user=request.user,
            author=obj
        ).exists()

    def get_recipes(self, obj):
        limit = self.context.get('recipes_limit')
        queryset = obj.recipes.all()
        if limit:
            try:
                queryset = queryset[:int(limit)]
            except ValueError:
                pass  # Игнорируем неверное значение
        return RecipeMinifiedSerializer(queryset, many=True).data

    def get_recipes_count(self, obj):
        return obj.recipes.count()


class RecipeShortLinkView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk=None):
        # Получаем рецепт или возвращаем 404
        recipe = get_object_or_404(Recipe, pk=pk)

        # Строим абсолютный URL для редиректа
        try:
            # Генерируем короткий код (используем ID как есть для простоты)
            short_code = str(recipe.id)

            # Получаем путь для редиректа
            redirect_path = reverse(
                'recipe_short_redirect',
                kwargs={'short_code': short_code}
            )

            # Строим абсолютный URL
            if settings.DEBUG:
                # Для разработки
                absolute_url = f"http://{request.get_host()}{redirect_path}"
            else:
                # Для продакшена с HTTPS
                absolute_url = f"https://{request.get_host()}{redirect_path}"

            # Возвращаем ответ
            return Response({"short-link": absolute_url}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"detail": f"Ошибка генерации ссылки: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RecipeShortRedirectView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, short_code):
        try:
            # Преобразуем код обратно в ID рецепта
            recipe_id = int(short_code)

            # Получаем рецепт или 404
            recipe = get_object_or_404(Recipe, pk=recipe_id)

            # Перенаправляем на детальную страницу рецепта
            recipe_url = reverse(
                'recipes-detail',
                kwargs={'pk': recipe.id}
            )

            if settings.DEBUG:
                full_url = f"http://{request.get_host()}{recipe_url}"
            else:
                full_url = f"https://{request.get_host()}{recipe_url}"

            return Response(
                {"Location": full_url},
                status=status.HTTP_302_FOUND,
                headers={"Location": full_url}
            )

        except ValueError:
            return Response(
                {"detail": "Неверный формат ссылки"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Recipe.DoesNotExist:
            return Response(
                {"detail": "Рецепт не найден"},
                status=status.HTTP_404_NOT_FOUND
            )


class RecipeMinifiedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')

    def get_image(self, obj):
        if obj.image:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return None


class IngredientViewSet(mixins.ListModelMixin,
                        mixins.RetrieveModelMixin,
                        viewsets.GenericViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    pagination_class = None
    filterset_class = IngredientFilter


class RecipeViewSet(viewsets.ModelViewSet):
    http_method_names = [
        'get', 'post', 'patch', 'delete',
        'head', 'options'
    ]
    queryset = Recipe.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnly]
    filterset_class = RecipeFilter

    def get_queryset(self):
        queryset = super().get_queryset()

        # Оптимизация для связанных данных
        queryset = queryset.select_related('author').prefetch_related(
            Prefetch(
                'ingredient_amounts',
                queryset=RecipeIngredient.objects.select_related('ingredient')
            ),
            'favorited_by',
            'in_shopping_carts'
        )

        # Аннотации для вычисляемых полей
        user = self.request.user
        if user.is_authenticated:
            queryset = queryset.annotate(
                is_favorited=Exists(
                    Favorite.objects.filter(
                        user=user,
                        recipe=OuterRef('pk')
                    )
                ),
                is_in_shopping_cart=Exists(
                    ShoppingCart.objects.filter(
                        user=user,
                        recipe=OuterRef('pk')
                    )
                )
            )
        return queryset

    def get_serializer_class(self):
        if self.action in ['create', 'partial_update']:
            return RecipeCreateUpdateSerializer
        return RecipeSerializer

    def create(self, request, *args, **kwargs):
        # Используем сериализатор для создания
        create_serializer = self.get_serializer(data=request.data)
        create_serializer.is_valid(raise_exception=True)
        self.perform_create(create_serializer)

        # Возвращаем результат через основной сериализатор
        instance = create_serializer.instance
        serializer = RecipeSerializer(instance, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        """Переопределяем partial_update для проверки авторства"""
        instance = self.get_object()
        if instance.author != request.user:
            return Response(
                {"detail": "Вы не являетесь автором этого рецепта"},
                status=status.HTTP_403_FORBIDDEN
            )

        partial = kwargs.pop('partial', True)  # Всегда частичное обновление для PATCH
        update_serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial
        )
        update_serializer.is_valid(raise_exception=True)
        self.perform_update(update_serializer)

        # 3. Возвращаем результат через основной RecipeSerializer
        instance.refresh_from_db()
        serializer = RecipeSerializer(instance, context={'request': request})

        return Response(serializer.data, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        """Блокируем стандартный update (PUT)"""
        return Response(
            {"detail": "Метод PUT не поддерживается. Используйте PATCH"},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.author != request.user:
            return Response(
                {"detail": "Вы не являетесь автором этого рецепта"},
                status=status.HTTP_403_FORBIDDEN
            )
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True, methods=['post', 'delete'], permission_classes=[IsAuthenticated])
    def favorite(self, request, pk=None):
        recipe = self.get_object()
        user = request.user

        if request.method == 'POST':
            _, created = Favorite.objects.get_or_create(user=user, recipe=recipe)
            if not created:
                return Response(
                    {'error': 'Рецепт уже в избранном'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            serializer = RecipeMinifiedSerializer(recipe, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        # DELETE
        favorite = Favorite.objects.filter(user=user, recipe=recipe)
        if not favorite.exists():
            return Response(
                {'error': 'Рецепта нет в избранном'},
                status=status.HTTP_400_BAD_REQUEST
            )
        favorite.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post', 'delete'], permission_classes=[IsAuthenticated])
    def shopping_cart(self, request, pk=None):
        recipe = self.get_object()
        user = request.user

        if request.method == 'POST':
            _, created = ShoppingCart.objects.get_or_create(user=user, recipe=recipe)
            if not created:
                return Response(
                    {'error': 'Рецепт уже в списке покупок'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            serializer = RecipeMinifiedSerializer(
                recipe, context={'request': request}
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        # DELETE
        cart_item = ShoppingCart.objects.filter(user=user, recipe=recipe)
        if not cart_item.exists():
            return Response(
                {'error': 'Рецепта нет в списке покупок'},
                status=status.HTTP_400_BAD_REQUEST
            )
        cart_item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def download_shopping_cart(self, request):
        user = request.user

        ingredients = RecipeIngredient.objects.filter(
            recipe__in_shopping_carts__user=user  # Измененная строка
        ).select_related('ingredient').values(
            'ingredient__name',
            'ingredient__measurement_unit'
        ).annotate(
            total_amount=Sum('amount')
        ).order_by('ingredient__name')

        if not ingredients:
            return HttpResponse("Ваш список покупок пуст", content_type='text/plain')

        # Формируем текстовый файл
        text = "Список покупок:\n\n"
        for item in ingredients:
            text += (
                f"{item['ingredient__name']} "
                f"({item['ingredient__measurement_unit']}) - "
                f"{item['total_amount']}\n"
            )

        response = HttpResponse(text, content_type='text/plain; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="shopping_list.txt"'
        return response