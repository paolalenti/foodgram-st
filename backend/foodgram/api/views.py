from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, Exists, OuterRef, Prefetch, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from djoser.views import UserViewSet as DjoserUserViewSet

from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
    IsAuthenticatedOrReadOnly
)
from rest_framework.response import Response
from rest_framework.views import APIView

from recipes.models import (
    Favorite,
    Ingredient,
    Recipe,
    RecipeIngredient,
    ShoppingCart
)

from .filters import IngredientFilter, RecipeFilter
from .pagination import CustomPageNumberPagination
from .permissions import IsAuthorOrReadOnly
from .serializers import (
    FavoriteSerializer, IngredientSerializer,
    RecipeCreateUpdateSerializer, RecipeSerializer,
    SetAvatarSerializer, SetPasswordSerializer,
    ShortCodeValidatorSerializer, ShoppingCartSerializer,
    SubscriptionSerializer, UserSerializer,
    UserWithRecipesSerializer,
)


User = get_user_model()


class UserViewSet(DjoserUserViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    @action(['post'],
            detail=False,
            permission_classes=[permissions.IsAuthenticated])
    def set_password(self, request):
        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(
                serializer.data['current_password']):
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

        if request.method == 'PUT':
            serializer = SetAvatarSerializer(
                user,
                data=request.data,
                context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(
                {'avatar': UserSerializer(
                    user,
                    context={'request': request}).data['avatar']},
                status=status.HTTP_200_OK
            )

        elif request.method == 'DELETE':
            if user.avatar:
                user.avatar.delete()

            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(['get'],
            detail=False,
            permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(['post'],
            detail=True,
            permission_classes=[permissions.IsAuthenticated])
    def subscribe(self, request, id=None):
        author = get_object_or_404(User, id=id)

        serializer = SubscriptionSerializer(
            data={'author': author.id},
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)

        recipes_limit = request.query_params.get('recipes_limit')
        response_serializer = UserWithRecipesSerializer(
            author,
            context={
                'request': request,
                'recipes_limit': recipes_limit
            }
        )
        return Response(response_serializer.data,
                        status=status.HTTP_201_CREATED)

    @subscribe.mapping.delete
    def unsubscribe(self, request, id=None):
        author = get_object_or_404(User, id=id)

        deleted_count, _ = request.user.following.filter(
            author=author
        ).delete()

        if deleted_count == 0:
            return Response(
                {'error': 'Вы не подписаны на этого автора'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(['get'], detail=False,
            permission_classes=[permissions.IsAuthenticated])
    def subscriptions(self, request):
        authors = User.objects.filter(
            followers__user=request.user
        ).annotate(
            recipes_count=Count('recipes')
        )

        paginator = CustomPageNumberPagination()

        result_page = paginator.paginate_queryset(authors, request)
        recipes_limit = request.query_params.get('recipes_limit')

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


class RecipeShortLinkView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk=None):
        recipe = get_object_or_404(Recipe, pk=pk)
        short_code = str(recipe.id)
        redirect_path = f'/r/{short_code}/'

        if settings.DEBUG:
            absolute_url = f'http://{request.get_host()}{redirect_path}'
        else:
            absolute_url = f'https://{request.get_host()}{redirect_path}'

        return Response(
            {'short-link': absolute_url},
            status=status.HTTP_200_OK
        )


class RecipeShortRedirectView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, short_code):
        recipe_queryset = Recipe.objects.all()
        serializer = ShortCodeValidatorSerializer(
            data={'short_code': short_code},
            recipe_queryset=recipe_queryset
        )
        if not serializer.is_valid():
            return Response(
                {'detail': ' '.join(
                    serializer.errors['short_code']
                )},
                status=status.HTTP_404_NOT_FOUND
            )

        recipe_id = serializer.validated_data['short_code']
        recipe_url = f'/recipes/{recipe_id}/'
        full_url = (f'http{"://" if settings.DEBUG else "s://"}'
                    f'{request.get_host()}{recipe_url}')

        return Response(
            {'Location': full_url},
            status=status.HTTP_302_FOUND,
            headers={'Location': full_url}
        )


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
    permission_classes = [IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]
    filterset_class = RecipeFilter

    def get_queryset(self):
        queryset = Recipe.objects.all().order_by('-pub_date')

        queryset = queryset.select_related('author').prefetch_related(
            Prefetch(
                'ingredient_amounts',
                queryset=RecipeIngredient.objects.select_related('ingredient')
            ),
            'favorited_by',
            'in_shopping_carts'
        )

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
        create_serializer = self.get_serializer(data=request.data)
        create_serializer.is_valid(raise_exception=True)
        self.perform_create(create_serializer)

        instance = create_serializer.instance
        serializer = RecipeSerializer(instance, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True,
            methods=['post', 'delete'],
            permission_classes=[IsAuthenticated])
    def favorite(self, request, pk=None):
        recipe = self.get_object()
        data = {'recipe': recipe.id}
        serializer = FavoriteSerializer(
            data=data, context={'request': request}
        )

        if request.method == 'POST':
            serializer.is_valid(raise_exception=True)
            serializer.save(user=request.user)
            return Response(
                serializer.data, status=status.HTTP_201_CREATED
            )

        if request.method == 'DELETE':
            if not Favorite.objects.filter(
                    user=request.user, recipe=recipe
            ).exists():
                return Response(
                    {'error': 'Рецепта нет в избранном'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            Favorite.objects.filter(
                user=request.user, recipe=recipe
            ).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True,
            methods=['post', 'delete'],
            permission_classes=[IsAuthenticated])
    def shopping_cart(self, request, pk=None):
        recipe = self.get_object()
        data = {'recipe': recipe.id}
        serializer = ShoppingCartSerializer(
            data=data, context={'request': request}
        )

        if request.method == 'POST':
            serializer.is_valid(raise_exception=True)
            serializer.save(user=request.user)
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )

        if request.method == 'DELETE':
            if not ShoppingCart.objects.filter(
                    user=request.user, recipe=recipe
            ).exists():
                return Response(
                    {'error': 'Рецепта нет в списке покупок'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            ShoppingCart.objects.filter(
                user=request.user, recipe=recipe
            ).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False,
            methods=['get'],
            permission_classes=[IsAuthenticated])
    def download_shopping_cart(self, request):
        user = request.user

        ingredients = RecipeIngredient.objects.filter(
            recipe__in_shopping_carts__user=user
        ).select_related('ingredient').values(
            'ingredient__name', 'ingredient__measurement_unit'
        ).annotate(
            total_amount=Sum('amount')
        ).order_by('ingredient__name')

        text = self.generate_shopping_list(ingredients)

        response = HttpResponse(
            text,
            content_type='text/plain; charset=utf-8'
        )
        response['Content-Disposition'] = ('attachment;'
                                           ' filename="shopping_list.txt"')
        return response

    def generate_shopping_list(self, ingredients):
        text = 'Список покупок:\n\n'
        for item in ingredients:
            text += (
                f'{item['ingredient__name']} '
                f'({item['ingredient__measurement_unit']}) - '
                f'{item['total_amount']}\n'
            )
        return text
