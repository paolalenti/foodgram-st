from django.contrib import admin
from django.urls import path, include

from api import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path(
        'r/<str:short_code>/',
        views.RecipeShortRedirectView.as_view(),
        name='recipe_short_redirect'
    ),
]
