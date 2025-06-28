from django.contrib import admin
from django.db.models import Count, Prefetch

from .models import (
    Recipe, Ingredient, RecipeIngredient,
    Favorite, ShoppingCart
)


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ('name', 'measurement_unit', 'recipe_count')
    search_fields = ('name',)
    ordering = ('name',)
    fields = ('name', 'measurement_unit')
    search_help_text = 'Поиск по названию ингредиента'

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            recipe_count=Count('recipe_amounts')
        )

    def recipe_count(self, obj):
        return obj.recipe_count

    recipe_count.short_description = 'Используется в рецептах'

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['name'].label = 'Название ингредиента'
        form.base_fields['measurement_unit'].label = 'Единица измерения'
        return form


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 1
    min_num = 1
    autocomplete_fields = ('ingredient',)
    verbose_name = 'Ингредиент'
    verbose_name_plural = 'Ингредиенты'

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        formset.form.base_fields['ingredient'].label_from_instance = (
            lambda inst: f'{inst.name} ({inst.measurement_unit})'
        )
        return formset


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'author', 'cooking_time',
        'pub_date', 'favorites_count', 'shopping_cart_count'
    )

    search_fields = ('name', 'author__username', 'author__email')
    search_help_text = 'Поиск по названию рецепта, имени автора или email'
    list_filter = ('pub_date', 'cooking_time')
    ordering = ('-pub_date',)
    inlines = (RecipeIngredientInline,)
    autocomplete_fields = ('author',)
    readonly_fields = ('pub_date', 'favorites_count', 'shopping_cart_count')

    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'author', 'image')
        }),
        ('Описание', {
            'fields': ('text',)
        }),
        ('Детали', {
            'fields': ('cooking_time', 'pub_date')
        }),
        ('Статистика', {
            'fields': ('favorites_count', 'shopping_cart_count')
        }),
    )

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .select_related('author')
            .prefetch_related(
                Prefetch(
                    'ingredient_amounts',
                    queryset=RecipeIngredient.objects.select_related(
                        'ingredient'
                    )
                )
            ).annotate(
                _favorites_count=Count('favorited_by'),
                _shopping_cart_count=Count('in_shopping_carts')
            )
        )

    def favorites_count(self, obj):
        return obj._favorites_count

    favorites_count.admin_order_field = '_favorites_count'
    favorites_count.short_description = 'В избранном'

    def shopping_cart_count(self, obj):
        return obj._shopping_cart_count

    shopping_cart_count.admin_order_field = '_shopping_cart_count'
    shopping_cart_count.short_description = 'В корзинах покупок'

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['name'].label = 'Название рецепта'
        form.base_fields['text'].label = 'Описание рецепта'
        form.base_fields['cooking_time'].label = 'Время приготовления (мин)'
        return form


@admin.register(RecipeIngredient)
class RecipeIngredientAdmin(admin.ModelAdmin):
    list_display = ('recipe', 'ingredient', 'amount', 'unit')
    search_fields = ('recipe__name', 'ingredient__name')
    list_filter = ('ingredient__measurement_unit',)
    autocomplete_fields = ('recipe', 'ingredient')

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .select_related('recipe', 'ingredient')
        )

    def unit(self, obj):
        return obj.ingredient.measurement_unit

    unit.short_description = 'Единица измерения'

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['amount'].label = 'Количество'
        return form


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'recipe')
    autocomplete_fields = ('user', 'recipe')
    search_fields = (
        'user__username', 'user__email',
        'recipe__name', 'recipe__author__username'
    )

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .select_related('user', 'recipe__author')
        )


@admin.register(ShoppingCart)
class ShoppingCartAdmin(admin.ModelAdmin):
    list_display = ('user', 'recipe')
    autocomplete_fields = ('user', 'recipe')
    search_fields = (
        'user__username', 'user__email',
        'recipe__name', 'recipe__author__username'
    )

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .select_related('user', 'recipe__author')
        )
