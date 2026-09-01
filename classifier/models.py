from django.db import models


class Category(models.Model):
    """
    A node in the Shopify Product Taxonomy tree (Q5). Self-referencing to
    represent the hierarchy, e.g. Furniture > Living Room Furniture > Sofas.

    Populated either by `seed_taxonomy` (a small bundled placeholder subset,
    for a zero-setup demo) or by `import_taxonomy` (a real Shopify taxonomy
    export you download and point the command at -- see README "Priority 3").
    """
    shopify_gid = models.CharField(max_length=255, unique=True, help_text="Shopify's canonical taxonomy GID, or a placeholder GID for the bundled demo subset")
    name = models.CharField(max_length=255)
    parent = models.ForeignKey("self", null=True, blank=True, related_name="children", on_delete=models.SET_NULL)
    full_path = models.CharField(max_length=500, db_index=True, help_text='Denormalized e.g. "Furniture > Living Room > Sofas"')
    level = models.PositiveSmallIntegerField(default=0)
    is_placeholder = models.BooleanField(default=True, help_text="True if seeded from the bundled demo subset rather than a real Shopify taxonomy export")

    class Meta:
        verbose_name_plural = "categories"

    def __str__(self):
        return self.full_path


class Attribute(models.Model):
    """An attribute definition (e.g. Color, Material) reusable across categories."""
    name = models.CharField(max_length=100)
    categories = models.ManyToManyField(Category, related_name="attributes", blank=True)

    def __str__(self):
        return self.name


class AttributeValue(models.Model):
    """A normalized, reusable value for an attribute (e.g. Attribute=Color, value="Gray")."""
    attribute = models.ForeignKey(Attribute, related_name="values", on_delete=models.CASCADE)
    value = models.CharField(max_length=150)

    class Meta:
        unique_together = ("attribute", "value")

    def __str__(self):
        return f"{self.attribute.name}: {self.value}"


class Product(models.Model):
    """Raw imported catalogue data -- one row per SKU, unchanged from the source file."""
    sku = models.CharField(max_length=100, unique=True, db_index=True)
    title = models.CharField(max_length=500, blank=True, default="")
    description = models.TextField(blank=True, default="")
    source_category = models.CharField(max_length=255, blank=True, default="")
    source_sub_category = models.CharField(max_length=255, blank=True, default="")
    product_type = models.CharField(
        max_length=255, blank=True, default="",
        help_text='From a source "Product Type" column when the catalogue has one; empty otherwise (this catalogue has none -- see README Priority 4)',
    )
    brand = models.CharField(max_length=255, blank=True, default="", help_text="Extracted from the title text (no structured Brand column in this catalogue)")
    image_url = models.URLField(max_length=1000, blank=True, default="", help_text="Primary image (first available image column)")
    image_urls = models.JSONField(default=list, blank=True, help_text="All available image URLs for this product (the catalogue provides up to 20)")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sku} - {self.title}"


class ClassificationJob(models.Model):
    """Tracks one batch-processing run (Q4, Q11)."""
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    total = models.PositiveIntegerField(default=0)
    done = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)
    needs_review = models.PositiveIntegerField(default=0)
    mode = models.CharField(
        max_length=20, default="sync",
        help_text="'sync' = processed in-process by the management command; 'celery' = dispatched to Celery workers",
    )

    def __str__(self):
        return f"Job #{self.id} ({self.started_at:%Y-%m-%d %H:%M})"


class ProductClassification(models.Model):
    """
    The system's classification output for a product. Decoupled from the raw
    Product row so re-classification never mutates source data (Q9).
    """
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("auto_classified", "Auto-classified"),
        ("needs_review", "Needs review"),
        ("approved", "Approved"),
        ("failed", "Failed"),
    ]

    product = models.OneToOneField(Product, related_name="classification", on_delete=models.CASCADE)
    job = models.ForeignKey(ClassificationJob, null=True, blank=True, related_name="classifications", on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    predicted_category = models.ForeignKey(Category, null=True, blank=True, related_name="+", on_delete=models.SET_NULL)
    confidence = models.PositiveSmallIntegerField(default=0)
    confidence_breakdown = models.JSONField(
        default=dict, blank=True,
        help_text="Weighted component scores that produced the final confidence (Q6) -- e.g. {'keyword': 40, 'semantic': 18, ...}",
    )
    reasoning = models.JSONField(
        default=list, blank=True,
        help_text='Human-readable evidence bullets for the UI, e.g. ["\'sofa\' found in title", "semantic similarity: 76%"]',
    )
    alternatives = models.JSONField(default=list, blank=True, help_text="Top alternative category suggestions (Q7)")
    layers_used = models.JSONField(default=list, blank=True, help_text="Which pipeline layers contributed to this result")
    failure_reason = models.CharField(max_length=255, blank=True, default="")
    reviewed_by = models.CharField(max_length=255, blank=True, default="")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.sku}: {self.status} ({self.confidence}%)"


class ProductAttributeValue(models.Model):
    """Many-to-many link: a classified product's detected attribute values, with per-attribute confidence."""
    classification = models.ForeignKey(ProductClassification, related_name="attribute_values", on_delete=models.CASCADE)
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE)
    value = models.ForeignKey(AttributeValue, on_delete=models.CASCADE)
    confidence = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = ("classification", "attribute")
