from django.urls import path
from classifier import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("api/products/", views.ProductClassificationListView.as_view(), name="product-list"),
    path("api/products/<int:product_id>/", views.ProductClassificationDetailView.as_view(), name="product-detail"),
    path("api/products/<int:product_id>/classification/", views.ProductClassificationUpdateView.as_view(), name="product-classification-update"),
]
