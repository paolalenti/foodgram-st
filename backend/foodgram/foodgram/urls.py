from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

from api import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path(
        'r/<str:short_code>/',
        views.RecipeShortRedirectView.as_view(),
        name='recipe_short_redirect'
    ),
    path('ws/', TemplateView.as_view(template_name='websocket_test.html')),
]
