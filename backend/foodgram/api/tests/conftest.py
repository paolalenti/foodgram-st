import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from recipes.models import Ingredient


User = get_user_model()


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    pass


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def authenticated_client(api_client):
    user = User.objects.create_user(
        email='test@example.com',
        first_name='test_first_name',
        last_name='test_last_name',
        username='testuser',
        password='testpassword123'
    )
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def sample_ingredient():
    return Ingredient.objects.create(name='Сахар', measurement_unit='г')


@pytest.fixture
def second_sample_ingredient():
    return Ingredient.objects.create(name='Соль', measurement_unit='г')


@pytest.fixture
def recipe_data(sample_ingredient):
    return {
        'ingredients': [
            {
                "id": sample_ingredient.id,
                "amount": 10
            }
        ],
        'name': 'Тестовый рецепт',
        'image': (
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAA'
            'IQAAAB6CAYAAAB+3PvOAAAAAXNSR0IArs4c6QAAAARnQU1B'
            'AACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAEmSUR'
            'BVHhe7dIxDcAwEMDAb/njzZpKVYaYw91iAn5m1h443lP4GY'
            'IwBGEIwhCEIQhDEIYgDEEYgjAEYQjCEIQhCEMQhiAMQRiCM'
            'ARhCMIQhCEIQxCGIAxBGIIwBGEIwhCEIQhDEIYgDEEYgjAE'
            'YQjCEIQhCEMQhiAMQRiCMARhCMIQhCEIQxCGIAxBGIIwBGE'
            'IwhCEIQhDEIYgDEEYgjAEYQjCEIQhCEMQhiAMQRiCMARhCM'
            'IQhCEIQxCGIAxBGIIwBGEIwhCEIQhDEIYgDEEYgjAEYQjCE'
            'IQhCEMQhiAMQRiCMARhCMIQhCEIQxCGIAxBGIIwBGEIwhCE'
            'IQhDEIYgDEEYgjAEYQjCEIQhCEMQhiAMQRiCMARhCMIQhCE'
            'IQxCGIAzBZeYDnHwC6fDGLJAAAAAASUVORK5CYII='
        ),
        'cooking_time': 30,
        'text': 'Описание тестового рецепта'
    }
