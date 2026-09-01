from django.core.management.base import BaseCommand
from django.db import transaction

from classifier.models import Category, Attribute, AttributeValue
from classifier.services.taxonomy_data import TAXONOMY


class Command(BaseCommand):
    help = (
        "Seeds the Category/Attribute/AttributeValue tables from the BUNDLED PLACEHOLDER "
        "taxonomy subset (a hand-built ~12-category demo set, not the real Shopify taxonomy). "
        "For the real Shopify taxonomy, download an export and use `import_taxonomy` instead "
        "-- see that command's docstring and README Priority 3."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        created = 0
        for key, cat in TAXONOMY.items():
            category, was_created = Category.objects.update_or_create(
                shopify_gid=f"gid://placeholder-taxonomy/{key}",
                defaults={
                    "name": cat["path"].split(">")[-1].strip(),
                    "full_path": cat["path"],
                    "level": cat["path"].count(">"),
                    "is_placeholder": True,
                },
            )
            created += int(was_created)

            for attr_name, values in cat["attributes"].items():
                attribute, _ = Attribute.objects.get_or_create(name=attr_name.capitalize())
                attribute.categories.add(category)
                for val in values:
                    AttributeValue.objects.get_or_create(attribute=attribute, value=val)

        # Brand is a genuine cross-category attribute (extracted from title text, not
        # tied to any single taxonomy leaf), so it isn't part of TAXONOMY's per-category
        # attribute lists -- seed it separately so attribute lookups succeed (Q6).
        Attribute.objects.get_or_create(name="Brand")

        self.stdout.write(self.style.SUCCESS(
            f"Seeded PLACEHOLDER taxonomy: {len(TAXONOMY)} categories ({created} newly created)."
        ))
        self.stdout.write(
            "This is a hand-built demo subset, not the real Shopify taxonomy. "
            "Run `python manage.py import_taxonomy <file>` with a real downloaded export "
            "for the actual Shopify category tree (see README Priority 3)."
        )
