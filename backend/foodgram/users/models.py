from django.contrib.auth.models import AbstractUser
from django.db import models


NAME_LENGTH = 150
EMAIL_LENGTH = 254


class User(AbstractUser):
    email = models.EmailField(
        'Email адрес',
        max_length=EMAIL_LENGTH,
        unique=True,
    )
    first_name = models.CharField('Имя', max_length=NAME_LENGTH)
    last_name = models.CharField('Фамилия', max_length=NAME_LENGTH)
    username = models.CharField(
        'Логин',
        max_length=NAME_LENGTH,
        unique=True
    )
    avatar = models.ImageField(
        'Аватар',
        upload_to='users/avatars/',
        default='',
        blank=True
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ['id']

    def __str__(self):
        return self.email


class Subscription(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='following',
        verbose_name='Подписчик'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='followers',
        verbose_name='Автор'
    )
    created = models.DateTimeField('Дата подписки', auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'author'],
                name='unique_subscription'
            )
        ]
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'

    def __str__(self):
        return f'{self.user} подписан на {self.author}'
