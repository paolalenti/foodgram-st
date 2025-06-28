import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.django_db
def test_create_recipe_authenticated(authenticated_client, recipe_data):
    url = reverse('recipes-list')
    response = authenticated_client.post(url, recipe_data, format='json')

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['name'] == 'Тестовый рецепт'
    assert response.data['author'] is not None


@pytest.mark.django_db
def test_create_recipe_unauthenticated(api_client, recipe_data):
    url = reverse('recipes-list')
    response = api_client.post(url, recipe_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_get_recipes_list(api_client, authenticated_client, recipe_data):
    url = reverse('recipes-list')
    authenticated_client.post(url, recipe_data, format='json')

    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) > 0
    assert any(
        r['name'] == 'Тестовый рецепт' for r in response.data['results']
    )
