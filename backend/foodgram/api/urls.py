from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()

# Регистрируем все ViewSets
router.register(r'users', views.UserViewSet,
                basename='users')
router.register(r'ingredients', views.IngredientViewSet,
                basename='ingredients')
router.register(r'recipes', views.RecipeViewSet,
                basename='recipes')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/', include('djoser.urls.authtoken')),
]
