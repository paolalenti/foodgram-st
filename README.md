# Foodgram - Социальная сеть для самых изысканных кулинаров!

Ссылка на репозиторий: https://github.com/paolalenti/foodgram-st/

## Запуск проекта

### Требования

- Docker
- Docker Compose
- Git

### 1. Клонирование репозитория

```bash
git clone https://github.com/paolalenti/foodgram-st/
cd foodgram-st
```

### 2. Настройка .env

Создайте файл .env в foodgram/infra (та же папка, где находится и 
docker-compose.yml)

```
SECRET_KEY='ksl1j=!iadt3-9#$5c3!9pi=0ipi-k2+9yqulr71n%iqj&*erf'
DJANGO_DEBUG = True
DJANGO_HOSTS = localhost, backend, 127.0.0.1

POSTGRES_DB=foodgram_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=DawnBreaker17

DB_ENGINE=django.db.backends.postgresql
DB_HOST=db
DB_PORT=5432
```

### 3. Запуск docker-compose.yml

Находясь в foodgram-st/infra, выполните следюущее:
```bash
docker-compose up --build
```

### 4. Заполнение базы данных
```bash
docker-compose exec backend python manage.py loaddata initial_data.json
```

В вашем распоряжении будут 2 обычных пользователя и суперпользователь 
admin@gmail.com.

Вот их данные для входа:
```
admin@gmail.com
Sigma123

cola@gmail.com
Sigma123

simple@gmail.com
Sigma123
```