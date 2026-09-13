import json

from django.conf import settings
from django.core.management.base import BaseCommand

from recipes.models import Ingredient


class Command(BaseCommand):
    """Управление загрузкой ингредиентов в базу данных."""

    help = "Загрузка ингредиентов из json файла в базу данных"

    def handle(self, *args, **options):
        file_path = settings.BASE_DIR / "data" / "ingredients.json"

        if not file_path.exists():
            self.stdout.write(
                self.style.ERROR(f"Файл не найден по пути: {file_path}")
            )
            return

        self.stdout.write("Начало загрузки ингредиентов...")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            ingredients_to_create = [
                Ingredient(
                    name=item["name"],
                    measurement_unit=item["measurement_unit"],
                )
                for item in data
            ]
            Ingredient.objects.bulk_create(
                ingredients_to_create, ignore_conflicts=True
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Успешно загружено ингредиентов: {Ingredient.objects.count()}"
            )
        )
