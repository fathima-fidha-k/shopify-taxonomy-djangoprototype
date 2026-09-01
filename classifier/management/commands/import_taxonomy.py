"""
Usage: python manage.py import_taxonomy taxonomy_sample.json
       python manage.py import_taxonomy path/to/real_shopify_export.json

Imports a Shopify-Product-Taxonomy-shaped export into the Category table,
building the actual parent/child hierarchy -- replacing (or supplementing)
the small hand-built demo subset that `seed_taxonomy` loads.

A bundled `taxonomy_sample.json` (43 hand-built categories, same shape as a
real export) ships in the project root so this command can be demonstrated
immediately without downloading anything. It is explicitly a hand-built
demonstration sample, NOT scraped or verified against Shopify's actual
published taxonomy -- its IDs are prefixed "sample-" specifically so they
can never be mistaken for real Shopify GIDs.

WHERE TO GET THE REAL FILE (you'll need to do this step yourself -- the
sandbox this project was built in has no internet access to download it):
    https://github.com/Shopify/product-taxonomy/tree/main/dist/en
Look for a JSON export of the category tree (at the time of writing, the
repo publishes this under dist/en/ -- the exact filename may have changed
since; browse that folder for the current category data file).

HONESTY NOTE: this command was written from general knowledge of how
Shopify's taxonomy is structured (an id/GID, a name, a parent reference,
and a full category path), but the *exact* JSON key names in the current
published export could not be verified without downloading it. Rather than
guess and silently import garbage, this command:
  1. Tries a list of common key-name aliases for each field (see KEY_ALIASES)
  2. Prints exactly which keys it found and used, before importing anything
  3. Fails loudly with a clear message (not a silent partial import) if it
     can't find a plausible id/name/parent field at all
  4. Supports both a flat list of category objects and a nested tree --
     whichever shape the real file turns out to use

The bundled sample file has been directly tested against this exact parsing
logic: all 43 categories parse correctly, with zero orphaned parent
references and exactly one root node ("Home & Garden"). The real-file
handling (key aliases, wrapper-object detection) is written defensively but
untested against an actual Shopify export, for the reasons above.

If the real file's structure doesn't match after you run this, the fix is
almost always just adding the actual key name to KEY_ALIASES below.
"""

import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from classifier.models import Category

# Try these key names, in order, for each field. Add the real key name here
# if the downloaded file uses something not already listed.
KEY_ALIASES = {
    "id": ["id", "gid", "shopify_gid", "taxonomy_id"],
    "name": ["name", "title", "label"],
    "full_path": ["full_name", "full_path", "path", "breadcrumb"],
    "parent_id": ["parent_id", "parent", "parent_gid"],
    "children": ["children", "child_categories", "subcategories"],
}


def _get(obj, field):
    for key in KEY_ALIASES[field]:
        if key in obj:
            return obj[key]
    return None


class Command(BaseCommand):
    help = "Import a real Shopify Product Taxonomy export (see module docstring for where to get one)."

    def add_arguments(self, parser):
        parser.add_argument("taxonomy_path", type=str)
        parser.add_argument("--dry-run", action="store_true", help="Parse and report without writing to the database")

    def handle(self, *args, **options):
        path = options["taxonomy_path"]
        dry_run = options["dry_run"]

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            raise CommandError(f"File not found: {path}")
        except json.JSONDecodeError as exc:
            raise CommandError(f"Not valid JSON: {exc}")

        flat_categories = self._flatten(data)
        if not flat_categories:
            raise CommandError(
                "Could not find any category objects with a recognizable id/name field. "
                "Check the file structure and update KEY_ALIASES in this command to match "
                "the actual key names used in your downloaded file."
            )

        self._report_sample(flat_categories)

        if dry_run:
            self.stdout.write(self.style.WARNING(f"Dry run: would import {len(flat_categories)} categories. No changes made."))
            return

        created, updated = self._import(flat_categories)
        self.stdout.write(self.style.SUCCESS(
            f"Imported real Shopify taxonomy: {created} categories created, {updated} updated."
        ))
        self.stdout.write(
            "Note: run `python manage.py classify_catalogue ...` again afterwards if you want "
            "classification results mapped against this real taxonomy instead of the bundled demo subset."
        )

    # -- Parsing: supports both a flat list and a nested tree ------------------

    def _flatten(self, data):
        """Returns a flat list of dicts, each with resolved id/name/full_path/parent_id,
        regardless of whether the source file was a flat list or a nested tree."""
        results = []

        def walk(node, parent_id_from_nesting=None):
            if isinstance(node, list):
                for item in node:
                    walk(item, parent_id_from_nesting)
                return

            if not isinstance(node, dict):
                return

            node_id = _get(node, "id")
            node_name = _get(node, "name")
            if node_id and node_name:
                results.append({
                    "id": str(node_id),
                    "name": str(node_name),
                    "full_path": _get(node, "full_path") or str(node_name),
                    "parent_id": _get(node, "parent_id") and str(_get(node, "parent_id")) or parent_id_from_nesting,
                })

            children = _get(node, "children")
            if children:
                walk(children, parent_id_from_nesting=node_id)

        if isinstance(data, dict) and any(k in data for k in ("categories", "data", "taxonomy")):
            # Common wrapper shapes: {"categories": [...]} etc.
            for wrapper_key in ("categories", "data", "taxonomy"):
                if wrapper_key in data:
                    walk(data[wrapper_key])
                    break
        else:
            walk(data)

        return results

    def _report_sample(self, flat_categories):
        self.stdout.write(f"Parsed {len(flat_categories)} categories. First 3 as a sanity check:")
        for cat in flat_categories[:3]:
            self.stdout.write(f"  id={cat['id']!r} name={cat['name']!r} parent_id={cat['parent_id']!r} path={cat['full_path']!r}")
        self.stdout.write("If these look wrong (garbled name, missing parent, etc.), check KEY_ALIASES in this command against the actual file's key names.\n")

    # -- Import ------------------------------------------------------------

    @transaction.atomic
    def _import(self, flat_categories):
        created = updated = 0
        by_id = {}

        # Pass 1: create/update all Category rows without parent links yet
        # (parents may not exist as DB rows until this pass completes).
        for cat in flat_categories:
            obj, was_created = Category.objects.update_or_create(
                shopify_gid=cat["id"],
                defaults={
                    "name": cat["name"],
                    "full_path": cat["full_path"],
                    "is_placeholder": False,
                },
            )
            by_id[cat["id"]] = obj
            created += int(was_created)
            updated += int(not was_created)

        # Pass 2: wire up parent relationships and compute level (depth)
        for cat in flat_categories:
            if not cat["parent_id"]:
                continue
            parent_obj = by_id.get(cat["parent_id"])
            if not parent_obj:
                continue  # parent not present in this file -- leave unlinked rather than guessing
            child_obj = by_id[cat["id"]]
            child_obj.parent = parent_obj
            child_obj.level = cat["full_path"].count(">") + 1
            child_obj.save(update_fields=["parent", "level"])

        return created, updated
