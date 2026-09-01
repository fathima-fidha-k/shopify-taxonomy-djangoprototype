from django.contrib import admin
from classifier.models import (
    Product, Category, Attribute, AttributeValue,
    ProductClassification, ProductAttributeValue, ClassificationJob,
)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("sku", "title", "brand", "product_type", "source_category", "source_sub_category")
    search_fields = ("sku", "title", "brand")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("full_path", "level", "is_placeholder")
    list_filter = ("is_placeholder",)


@admin.register(ProductClassification)
class ProductClassificationAdmin(admin.ModelAdmin):
    list_display = ("product", "status", "predicted_category", "confidence", "reviewed_by")
    list_filter = ("status",)
    search_fields = ("product__sku", "product__title")


admin.site.register(Attribute)
admin.site.register(AttributeValue)
admin.site.register(ProductAttributeValue)
admin.site.register(ClassificationJob)
