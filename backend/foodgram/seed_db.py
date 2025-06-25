import json

with open('../../data/ingredients.json') as f:
    original_data = json.load(f)

# Преобразование в формат фикстуры
fixture_data = []
for idx, item in enumerate(original_data, start=1):
    fixture_data.append({
        "model": "recipes.ingredient",
        "pk": idx,
        "fields": {
            "name": item["name"],
            "measurement_unit": item["measurement_unit"]
        }
    })

# Сохранение нового файла
with open('ingredients_for_db.json', 'w') as f:
    json.dump(fixture_data, f, indent=2, ensure_ascii=False)
