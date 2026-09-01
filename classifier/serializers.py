from rest_framework import serializers
from classifier.models import Product, ProductClassification, ProductAttributeValue


class AttributeValueSerializer(serializers.ModelSerializer):
    attribute = serializers.CharField(source="attribute.name")
    value = serializers.CharField(source="value.value")

    class Meta:
        model = ProductAttributeValue
        fields = ["attribute", "value", "confidence"]


class ProductClassificationSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source="product.sku")
    title = serializers.CharField(source="product.title")
    description = serializers.CharField(source="product.description")
    image_url = serializers.CharField(source="product.image_url")
    image_urls = serializers.ListField(source="product.image_urls", child=serializers.CharField(), default=list)
    product_type = serializers.CharField(source="product.product_type")
    brand = serializers.CharField(source="product.brand")
    source_category = serializers.CharField(source="product.source_category")
    source_sub_category = serializers.CharField(source="product.source_sub_category")
    predicted_path = serializers.CharField(source="predicted_category.full_path", allow_null=True)
    attributes = AttributeValueSerializer(source="attribute_values", many=True, read_only=True)

    class Meta:
        model = ProductClassification
        fields = [
            "id", "sku", "title", "description", "image_url", "image_urls",
            "product_type", "brand", "source_category", "source_sub_category",
            "status", "predicted_path", "confidence", "confidence_breakdown", "reasoning",
            "alternatives", "layers_used",
            "failure_reason", "attributes", "reviewed_by", "reviewed_at", "updated_at",
        ]


class ClassificationUpdateSerializer(serializers.Serializer):
    """Body for PATCH /api/products/{id}/classification/ -- human approve/correct (Q9)."""
    category_path = serializers.CharField(required=False, allow_null=True)
    status = serializers.ChoiceField(
        choices=["approved", "needs_review", "auto_classified"], required=False
    )
    reviewed_by = serializers.CharField(required=False, allow_blank=True)
