import requests
import secrets
import random
import string
import logging

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.db.models import Count, Exists, OuterRef, Prefetch, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from djoser.views import UserViewSet as DjoserUserViewSet

from rest_framework import mixins, permissions, status, viewsets
from rest_framework.authtoken.models import Token
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


logger = logging.getLogger(__name__)

User = get_user_model()


def github_login(request):
    # Генерация уникального state
    state = secrets.token_urlsafe(16)
    request.session['github_oauth_state'] = state
    request.session.save()  # Важно: сохраняем сессию

    # Формирование URL для перенаправления
    auth_url = (
        f"{settings.GITHUB_AUTHORIZE_URL}?"
        f"client_id={settings.GITHUB_CLIENT_ID}&"
        f"redirect_uri={settings.GITHUB_REDIRECT_URI}&"
        f"scope=user:email&"
        f"state={state}"
    )
    return redirect(auth_url)


def github_callback(request):
    # Проверка state
    saved_state = request.session.get('github_oauth_state')
    if not saved_state or request.GET.get('state') != saved_state:
        logger.error(
            f"Invalid state: saved={saved_state},"
            f" received={request.GET.get('state')}"
        )
        return HttpResponse('Invalid state parameter', status=400)

    # Удаление использованного state
    del request.session['github_oauth_state']
    request.session.save()

    # Получение кода
    code = request.GET.get('code')
    if not code:
        return HttpResponse('No code provided', status=400)

    # Создание сессии для сохранения cookies
    session = requests.Session()

    # Подготовка данных для запроса токена
    token_data = {
        'client_id': settings.GITHUB_CLIENT_ID,
        'client_secret': settings.GITHUB_CLIENT_SECRET,
        'code': code,
        'redirect_uri': settings.GITHUB_REDIRECT_URI
    }

    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

    try:
        # Запрос access token
        token_response = session.post(
            settings.GITHUB_TOKEN_URL,
            json=token_data,
            headers=headers
        )

        logger.debug(
            f"Token response: {token_response.status_code} -"
            f" {token_response.text}"
        )

        if token_response.status_code != 200:
            return HttpResponse(
                f"GitHub token error: {token_response.status_code} -"
                f" {token_response.text}",
                status=400
            )

        token_json = token_response.json()
        access_token = token_json.get('access_token')

        if not access_token:
            return HttpResponse(
                "Access token not found in response",
                status=400
            )

        # Получение данных пользователя с использованием той же сессии
        user_headers = {
            'Authorization': f'token {access_token}',
            'Accept': 'application/json'
        }
        user_response = session.get(
            settings.GITHUB_USER_URL,
            headers=user_headers
        )

        logger.debug(
            f"User response: {user_response.status_code} - "
            f"{user_response.text}"
        )

        if user_response.status_code != 200:
            return HttpResponse(
                f"GitHub user error: {user_response.status_code} - "
                f"{user_response.text}",
                status=400
            )

        user_data = user_response.json()

        # Получение email
        email = user_data.get('email')
        if not email:
            emails_response = session.get(
                'https://api.github.com/user/emails',
                headers=user_headers
            )
            if emails_response.status_code == 200:
                emails = emails_response.json()
                primary_emails = [
                    e['email'] for e in emails
                    if e.get('primary') and e.get('verified')
                ]
                if primary_emails:
                    email = primary_emails[0]

        if not email:
            return HttpResponse(
                "Email not found and couldn't be generated",
                status=400
            )

        # Обработка имени
        name_parts = (user_data.get('name', '').split(' ', 1)
                      if user_data.get('name')
                      else [user_data['login'], ''])
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        # Поиск или создание пользователя
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Генерация уникального username
            base_username = user_data['login']
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}_{counter}"
                counter += 1

            # Генерация случайного пароля
            password = ''.join(random.choices(
                string.ascii_letters + string.digits + string.punctuation,
                k=20
            ))

            # Создание пользователя
            user = User.objects.create_user(
                email=email,
                username=username,
                first_name=first_name,
                last_name=last_name,
                password=password
            )
        # Аутентификация пользователя
        login(request, user)
        token, created = Token.objects.get_or_create(user=user)
        request.session['auth_token'] = token.key
        return redirect('http://localhost/api/set_token/')

    except Exception as e:
        logger.exception("GitHub OAuth error")
        return HttpResponse(f"Error: {str(e)}", status=500)


def set_token_view(request):
    # Получаем токен из сессии
    token = request.session.get('auth_token')

    if not token:
        # Если токена нет, перенаправляем на страницу ошибки
        return redirect('login_error')  # Создайте эту view

    # Удаляем токен из сессии после использования
    if 'auth_token' in request.session:
        del request.session['auth_token']

    # Рендерим страницу, которая установит токен и перенаправит
    return render(request, 'set_token.html', {
        'token': token,
        'redirect_url': 'http://localhost/recipes/'
    })


class UserViewSet(DjoserUserViewSet):
    """CRUD для пользователя и создание/удаление подписок."""

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
    """Получение короткой ссылки для рецепта."""

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
    """Перенаправление короткой ссылки на полный URL рецепта."""

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
    """Работа с ингредиентами."""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    pagination_class = None
    filterset_class = IngredientFilter


class RecipeViewSet(viewsets.ModelViewSet):
    """CRUD для рецептов, работа с избранным и корзиной."""

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

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[IsAuthenticated])
    def favorite(self, request, pk=None):
        return self._handle_relation(
            request,
            pk=pk,
            serializer_class=FavoriteSerializer,
            model_class=Favorite,
            not_found_message='Рецепта нет в избранном'
        )

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[IsAuthenticated]
    )
    def shopping_cart(self, request, pk=None):
        return self._handle_relation(
            request,
            pk=pk,
            serializer_class=ShoppingCartSerializer,
            model_class=ShoppingCart,
            not_found_message='Рецепта нет в списке покупок'
        )

    def _handle_relation(
            self, request, pk,
            serializer_class, model_class,
            not_found_message
    ):
        recipe = self.get_object()
        data = {'recipe': recipe.id}
        serializer = serializer_class(data=data, context={'request': request})

        if request.method == 'POST':
            serializer.is_valid(raise_exception=True)
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if request.method == 'DELETE':
            deleted_count, _ = model_class.objects.filter(
                user=request.user,
                recipe=recipe
            ).delete()
            if deleted_count == 0:
                return Response(
                    {'error': not_found_message},
                    status=status.HTTP_400_BAD_REQUEST
                )

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
