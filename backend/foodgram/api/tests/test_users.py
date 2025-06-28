import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.django_db
def test_user_registration(api_client):
    url = reverse('users-list')
    data = {
        'email': 'newuser@example.com',
        'first_name': 'newuser_first_name',
        'last_name': 'newuser_last_name',
        'username': 'newuser',
        'password': 'newuserpassword123'
    }
    response = api_client.post(url, data)
    assert response.status_code == status.HTTP_201_CREATED
    assert 'id' in response.data
    assert response.data['email'] == 'newuser@example.com'


@pytest.mark.django_db
def test_user_list_unauthorized(api_client):
    url = reverse('users-list')
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.data['results'], list)


@pytest.mark.django_db
def test_user_list_authorized(authenticated_client):
    url = reverse('users-list')
    response = authenticated_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.data['results'], list)
