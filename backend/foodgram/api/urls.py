from django.urls import include, path
from django.views.generic import TemplateView

from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()

router.register(r'users', views.UserViewSet,
                basename='users')
router.register(r'ingredients', views.IngredientViewSet,
                basename='ingredients')
router.register(r'recipes', views.RecipeViewSet,
                basename='recipes')

urlpatterns = [
    path('', include(router.urls)),
    path(
        'recipes/<int:pk>/get-link/',
        views.RecipeShortLinkView.as_view(),
        name='recipe-get-link'
    ),
    path('auth/', include('djoser.urls.authtoken')),
    path(
        'login/github/',
        TemplateView.as_view(template_name='github_login.html'),
        name='github_login_page'
    ),
    path('oauth/github/login/', views.github_login, name='github_login'),
    path(
        'oauth/github/callback/',
        views.github_callback,
        name='github_callback'
    ),
    path('set_token/', views.set_token_view, name='set_token'),
]
