from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User, Subscription


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        'email', 'username', 'first_name',
        'last_name', 'is_staff', 'is_active'
    )

    search_fields = ('email', 'username')

    list_filter = ('is_staff', 'is_superuser', 'is_active')

    ordering = ('email',)

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

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 'username', 'first_name',
                'last_name', 'password1', 'password2'
            ),
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        is_superuser = request.user.is_superuser

        if not is_superuser:
            disabled_fields = {'is_superuser', 'user_permissions'}
            for field in disabled_fields:
                if field in form.base_fields:
                    form.base_fields[field].disabled = True

        return form


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'author', 'created')

    autocomplete_fields = ('user', 'author')

    search_fields = (
        'user__email',
        'user__username',
        'author__email',
        'author__username'
    )

    list_filter = ('created',)

    list_select_related = ('user', 'author')

    fields = ('user', 'author', 'created')
    readonly_fields = ('created',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name in ['user', 'author']:
            kwargs['queryset'] = User.objects.order_by('email')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
