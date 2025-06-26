from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator

from djoser.serializers import UserCreateSerializer

from rest_framework import serializers

from recipes.models import (
    Favorite,
    Ingredient,
    Recipe,
    RecipeIngredient,
    ShoppingCart
)
from users.models import Subscription


User = get_user_model()


class ShoppingCartSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShoppingCart
        fields = ['user', 'recipe']
        extra_kwargs = {
            'user': {'read_only': True},
            'recipe': {'required': True}
        }

    def validate_recipe(self, value):
        user = self.context['request'].user
        if ShoppingCart.objects.filter(user=user, recipe=value).exists():
            raise serializers.ValidationError('Рецепт уже в списке покупок')
        return value

    def to_representation(self, instance):
        recipe = instance.recipe
        return RecipeMinifiedSerializer(
            recipe, context=self.context
        ).data


class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorite
        fields = ('user', 'recipe')
        extra_kwargs = {
            'user': {'read_only': True},
            'recipe': {'required': True}
        }

    def validate_recipe(self, value):
        user = self.context['request'].user
        if Favorite.objects.filter(user=user, recipe=value).exists():
            raise (serializers.
                   ValidationError('Рецепт уже в избранном'))
        return value

    def to_representation(self, instance):
        recipe = instance.recipe
        return RecipeMinifiedSerializer(
            recipe, context=self.context
        ).data


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ('user', 'author')
        extra_kwargs = {
            'user': {'read_only': True},
            'author': {'required': True}
        }

    def validate_author(self, value):
        user = self.context['request'].user

        if user == value:
            raise serializers.ValidationError(
                'Нельзя подписаться на самого себя')

        if Subscription.objects.filter(
                user=user, author=value
        ).exists():
            raise serializers.ValidationError(
                'Вы уже подписаны на этого автора')

        return value


class UserWithRecipesSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.IntegerField(
        read_only=True,
        default=0
    )
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'email', 'id', 'username', 'first_name',
            'last_name', 'is_subscribed', 'recipes',
            'recipes_count', 'avatar'
        )

    def get_avatar(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            return (
                request.build_absolute_uri(obj.avatar.url)
                if request else obj.avatar.url
            )
        return None

    def get_is_subscribed(self, obj):
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
            if isinstance(limit, int):
                queryset = queryset[:limit]
            elif isinstance(limit, str) and limit.isdigit():
                queryset = queryset[:int(limit)]

        return RecipeMinifiedSerializer(queryset, many=True).data

    def get_recipes_count(self, obj):
        return obj.recipes.count()


class RecipeMinifiedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')

    def get_image(self, obj):
        if obj.image:
            request = self.context.get('request')
            return (
                request.build_absolute_uri(obj.image.url)
                if request else obj.image.url
            )
        return None


class ShortCodeValidatorSerializer(serializers.Serializer):
    short_code = serializers.CharField()

    def __init__(self, *args, **kwargs):
        self.recipe_queryset = kwargs.pop(
            'recipe_queryset', Recipe.objects.all()
        )
        super().__init__(*args, **kwargs)

    def validate_short_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError('Неверный формат ссылки')

        recipe_id = int(value)

        if not self.recipe_queryset.filter(pk=recipe_id).exists():
            raise serializers.ValidationError('Рецепт не найден')

        return recipe_id


class ShortLinkSerializer(serializers.Serializer):
    short_link = serializers.URLField(read_only=True)

    def to_representation(self, instance):
        return {
            'short-link': instance
        }


class Base64ImageField(serializers.ImageField):

    def to_internal_value(self, data):
        import base64
        from django.core.files.base import ContentFile

        if isinstance(data, str) and data.startswith('data:image'):
            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1]
            data = ContentFile(base64.b64decode(imgstr), name=f'temp.{ext}')
            if data.size > 2 * 1024 * 1024:  # 2MB
                raise serializers.ValidationError(
                    'Размер изображения не должен превышать 2MB')

        return super().to_internal_value(data)


class CustomUserCreateSerializer(UserCreateSerializer):
    username = serializers.CharField(
        validators=[RegexValidator(r'^[\w.@+-]+\Z')],
        max_length=150
    )

    class Meta(UserCreateSerializer.Meta):
        model = User
        fields = (
            'email', 'id', 'username',
            'first_name', 'last_name', 'password'
        )
        extra_kwargs = {'password': {'write_only': True}}


class UserSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('email', 'id', 'username', 'first_name',
                  'last_name', 'is_subscribed', 'avatar')

    def get_avatar(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            return (
                request.build_absolute_uri(obj.avatar.url)
                if request else obj.avatar.url
            )
        return None

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False

        return Subscription.objects.filter(
            user=request.user,
            author=obj
        ).exists()


class SetPasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)


class SetAvatarSerializer(serializers.ModelSerializer):
    avatar = Base64ImageField(required=True)

    class Meta:
        model = User
        fields = ('avatar',)


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class RecipeIngredientSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(
        source='ingredient.measurement_unit')

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    ingredients = RecipeIngredientSerializer(
        source='ingredient_amounts',
        many=True,
        read_only=True
    )
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    image = Base64ImageField(required=False)

    class Meta:
        model = Recipe
        fields = (
            'id', 'author', 'name', 'image', 'text',
            'cooking_time', 'ingredients',
            'is_favorited', 'is_in_shopping_cart'
        )

    def get_is_favorited(self, obj):
        user = self.context['request'].user
        if user.is_authenticated:
            return obj.favorited_by.filter(user=user).exists()
        return False

    def get_is_in_shopping_cart(self, obj):
        user = self.context['request'].user
        if user.is_authenticated:
            return obj.in_shopping_carts.filter(user=user).exists()
        return False


class RecipeCreateUpdateSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=True, max_length=256)
    ingredients = serializers.JSONField(
        required=True,
        write_only=True
    )
    image = Base64ImageField(required=False)
    text = serializers.CharField(required=True)
    cooking_time = serializers.IntegerField(
        required=True, min_value=1,
        error_messages={
            'min_value': 'Время приготовления должно быть не менее'
                         ' 1 минуты'
        }
    )

    class Meta:
        model = Recipe
        fields = (
            'id', 'name', 'image', 'text',
            'cooking_time', 'ingredients'
        )
        read_only_fields = ('author',)

    def validate_ingredients(self, value):
        if not value:
            raise serializers.ValidationError('Необходим хотя бы один'
                                              ' ингредиент')

        for item in value:
            if 'id' not in item or 'amount' not in item:
                raise serializers.ValidationError(
                    'Каждый ингредиент должен содержать "id" и '
                    '"amount"'
                )

        ingredient_ids = [item['id'] for item in value]
        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError('Ингредиенты не должны'
                                              ' повторяться')

        existing_ids = set(Ingredient.objects.filter(
            id__in=ingredient_ids
        ).values_list('id', flat=True))

        missing_ids = set(ingredient_ids) - existing_ids
        if missing_ids:
            raise serializers.ValidationError(
                f'Ингредиенты с ID {', '.join(map(str, missing_ids))}'
                f' не существуют'
            )

        for item in value:
            amount = item['amount']
            if not isinstance(amount, int):
                if not amount.isdigit():
                    raise serializers.ValidationError(
                        f'Количество ингредиента ID {item['id']} '
                        f'должно быть целым числом больше 0'
                    )
                amount = int(amount)
            if amount < 1:
                raise serializers.ValidationError(
                    f'Количество ингредиента ID {item['id']} '
                    f'должно быть целым числом больше 0'
                )

        return value

    def create_ingredients(self, recipe, ingredients):
        objs = []
        for ingredient in ingredients:
            objs.append(RecipeIngredient(
                recipe=recipe,
                ingredient_id=ingredient['id'],
                amount=int(ingredient['amount'])
            ))
        RecipeIngredient.objects.bulk_create(objs)

    def validate(self, data):
        cooking_time = data.get('cooking_time')
        if cooking_time and cooking_time < 1:
            raise serializers.ValidationError({
                'cooking_time': 'Время приготовления должно быть не '
                                'менее 1 минуты'
            })

        if self.context['request'].method == 'POST':
            if 'image' not in data:
                raise serializers.ValidationError({
                    'image': 'Это поле обязательно при создании рецепта'
                })

            # Для PATCH проверяем наличие обязательных полей, кроме image
        if self.context['request'].method == 'PATCH':
            required_fields = [
                'ingredients', 'name', 'text', 'cooking_time'
            ]
            missing_fields = [
                field for field in required_fields if field not in data
            ]

            if missing_fields:
                raise serializers.ValidationError({
                    'required_fields': f'При обновлении обязательны поля:'
                                       f' {', '.join(missing_fields)}'
                })

        return data

    def create(self, validated_data):
        ingredients = validated_data.pop('ingredients')

        recipe = Recipe.objects.create(
            **validated_data
        )
        self.create_ingredients(recipe, ingredients)
        return recipe

    def update(self, instance, validated_data):
        ingredients = validated_data.pop('ingredients', None)

        instance = super().update(instance, validated_data)

        if ingredients is not None:
            instance.ingredient_amounts.all().delete()
            self.create_ingredients(instance, ingredients)

        return instance

    def to_representation(self, instance):
        return RecipeSerializer(instance, context=self.context).data
