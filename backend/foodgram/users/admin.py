from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Subscription


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    # Отображаемые поля в списке пользователей
    list_display = (
        'email', 'username', 'first_name',
        'last_name', 'is_staff', 'is_active'
    )

    # Поля для поиска
    search_fields = ('email', 'username')

    # Фильтры
    list_filter = ('is_staff', 'is_superuser', 'is_active')

    # Порядок сортировки
    ordering = ('email',)

    # Настройка полей на странице редактирования пользователя
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Персональная информация',
         {'fields': ('username', 'first_name', 'last_name', 'avatar')}),
        ('Права доступа', {
            'fields': ('is_active', 'is_staff',
                       'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Важные даты', {'fields': ('last_login', 'date_joined')}),
    )

    # Настройка полей при создании нового пользователя
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 'username', 'first_name',
                'last_name', 'password1', 'password2'
            ),
        }),
    )

    # Добавляем кастомные поля в форму редактирования
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        is_superuser = request.user.is_superuser

        # Для суперпользователя показываем все поля
        if not is_superuser:
            # Ограничиваем права для обычных администраторов
            disabled_fields = {'is_superuser', 'user_permissions'}
            for field in disabled_fields:
                if field in form.base_fields:
                    form.base_fields[field].disabled = True

        return form


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    # Отображаемые поля в списке подписок
    list_display = ('user', 'author', 'created')

    # Автодополнение для полей выбора пользователей
    autocomplete_fields = ('user', 'author')

    # Поиск по связанным пользователям
    search_fields = (
        'user__email',
        'user__username',
        'author__email',
        'author__username'
    )

    # Фильтры
    list_filter = ('created',)

    # Оптимизация запросов
    list_select_related = ('user', 'author')

    # Настройка полей на странице редактирования
    fields = ('user', 'author', 'created')
    readonly_fields = ('created',)

    # Кастомный метод для отображения пользователей
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Ограничиваем выбор пользователей для полей user и author
        if db_field.name in ['user', 'author']:
            kwargs["queryset"] = User.objects.order_by('email')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
