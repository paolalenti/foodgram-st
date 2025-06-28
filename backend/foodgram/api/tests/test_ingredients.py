import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.django_db
def test_ingredient_list(api_client, sample_ingredient):
    url = reverse('ingredients-list')
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) > 0
    assert any(i['name'] == sample_ingredient.name for i in response.data)


@pytest.mark.django_db
def test_ingredient_search(api_client, sample_ingredient,
                           second_sample_ingredient):
    url = reverse('ingredients-list')
    response = api_client.get(url, {'name': second_sample_ingredient.name})

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]['name'] == 'Соль'
