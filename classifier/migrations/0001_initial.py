import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("shopify_gid", models.CharField(help_text="Shopify's canonical taxonomy GID, or a placeholder GID for the bundled demo subset", max_length=255, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("full_path", models.CharField(db_index=True, help_text='Denormalized e.g. "Furniture > Living Room > Sofas"', max_length=500)),
                ("level", models.PositiveSmallIntegerField(default=0)),
                ("is_placeholder", models.BooleanField(default=True, help_text="True if seeded from the bundled demo subset rather than a real Shopify taxonomy export")),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="children", to="classifier.category")),
            ],
            options={"verbose_name_plural": "categories"},
        ),
        migrations.CreateModel(
            name="Attribute",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("categories", models.ManyToManyField(blank=True, related_name="attributes", to="classifier.category")),
            ],
        ),
        migrations.CreateModel(
            name="AttributeValue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("value", models.CharField(max_length=150)),
                ("attribute", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="values", to="classifier.attribute")),
            ],
            options={"unique_together": {("attribute", "value")}},
        ),
        migrations.CreateModel(
            name="Product",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sku", models.CharField(db_index=True, max_length=100, unique=True)),
                ("title", models.CharField(blank=True, default="", max_length=500)),
                ("description", models.TextField(blank=True, default="")),
                ("source_category", models.CharField(blank=True, default="", max_length=255)),
                ("source_sub_category", models.CharField(blank=True, default="", max_length=255)),
                ("product_type", models.CharField(blank=True, default="", help_text='From a source "Product Type" column when the catalogue has one; empty otherwise (this catalogue has none -- see README Priority 4)', max_length=255)),
                ("brand", models.CharField(blank=True, default="", help_text="Extracted from the title text (no structured Brand column in this catalogue)", max_length=255)),
                ("image_url", models.URLField(blank=True, default="", help_text="Primary image (first available image column)", max_length=1000)),
                ("image_urls", models.JSONField(blank=True, default=list, help_text="All available image URLs for this product (the catalogue provides up to 20)")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="ClassificationJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("total", models.PositiveIntegerField(default=0)),
                ("done", models.PositiveIntegerField(default=0)),
                ("failed", models.PositiveIntegerField(default=0)),
                ("needs_review", models.PositiveIntegerField(default=0)),
                ("mode", models.CharField(default="sync", help_text="'sync' = processed in-process by the management command; 'celery' = dispatched to Celery workers", max_length=20)),
            ],
        ),
        migrations.CreateModel(
            name="ProductClassification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "Pending"), ("processing", "Processing"), ("auto_classified", "Auto-classified"), ("needs_review", "Needs review"), ("approved", "Approved"), ("failed", "Failed")], db_index=True, default="pending", max_length=20)),
                ("confidence", models.PositiveSmallIntegerField(default=0)),
                ("confidence_breakdown", models.JSONField(blank=True, default=dict, help_text="Weighted component scores that produced the final confidence (Q6) -- e.g. {'keyword': 40, 'semantic': 18, ...}")),
                ("reasoning", models.JSONField(blank=True, default=list, help_text='Human-readable evidence bullets for the UI, e.g. ["\'sofa\' found in title", "semantic similarity: 76%"]')),
                ("alternatives", models.JSONField(blank=True, default=list, help_text="Top alternative category suggestions (Q7)")),
                ("layers_used", models.JSONField(blank=True, default=list, help_text="Which pipeline layers contributed to this result")),
                ("failure_reason", models.CharField(blank=True, default="", max_length=255)),
                ("reviewed_by", models.CharField(blank=True, default="", max_length=255)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("job", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="classifications", to="classifier.classificationjob")),
                ("predicted_category", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="classifier.category")),
                ("product", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="classification", to="classifier.product")),
            ],
        ),
        migrations.CreateModel(
            name="ProductAttributeValue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("confidence", models.PositiveSmallIntegerField(default=0)),
                ("attribute", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="classifier.attribute")),
                ("classification", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attribute_values", to="classifier.productclassification")),
                ("value", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="classifier.attributevalue")),
            ],
            options={"unique_together": {("classification", "attribute")}},
        ),
    ]
