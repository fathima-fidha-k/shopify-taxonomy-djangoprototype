from django.shortcuts import render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Q
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response

from classifier.models import ProductClassification, Category
from classifier.serializers import ProductClassificationSerializer, ClassificationUpdateSerializer


class ProductClassificationListView(generics.ListAPIView):
    """GET /api/products/?status=needs_review -- paginated, filterable list (Q9)."""
    serializer_class = ProductClassificationSerializer

    def get_queryset(self):
        qs = ProductClassification.objects.select_related("product", "predicted_category").prefetch_related(
            "attribute_values__attribute", "attribute_values__value"
        ).order_by("id")
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class ProductClassificationDetailView(generics.RetrieveAPIView):
    """GET /api/products/{id}/ -- full detail including alternative suggestions (Q9)."""
    serializer_class = ProductClassificationSerializer
    queryset = ProductClassification.objects.select_related("product", "predicted_category").prefetch_related(
        "attribute_values__attribute", "attribute_values__value"
    )
    lookup_field = "product_id"
    lookup_url_kwarg = "product_id"


@method_decorator(csrf_exempt, name="dispatch")
class ProductClassificationUpdateView(APIView):
    """PATCH /api/products/{id}/classification/ -- human approves/corrects the result (Q9).

    csrf_exempt for prototype convenience so the dashboard's approve/reject
    buttons can call this via a plain fetch() without wiring up a CSRF token
    flow. In production, this endpoint would sit behind normal session/API
    auth and CSRF protection would be re-enabled (or a token-based auth
    scheme, which is CSRF-exempt by nature, would be used instead).
    """

    def patch(self, request, product_id):
        try:
            classification = ProductClassification.objects.get(product_id=product_id)
        except ProductClassification.DoesNotExist:
            return Response({"error": "not found"}, status=status.HTTP_404_NOT_FOUND)

        payload = ClassificationUpdateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        if "category_path" in data and data["category_path"]:
            try:
                classification.predicted_category = Category.objects.get(full_path=data["category_path"])
            except Category.DoesNotExist:
                return Response({"error": "unknown category_path"}, status=status.HTTP_400_BAD_REQUEST)

        classification.status = data.get("status", "approved")
        classification.reviewed_by = data.get("reviewed_by", classification.reviewed_by)
        classification.reviewed_at = timezone.now()
        classification.save()

        return Response(ProductClassificationSerializer(classification).data)


def dashboard(request):
    """A review dashboard: product -> predicted category -> confidence (with 'why') -> alternatives -> attributes -> approve/correct (Q9, Priority 12).

    Priority 4 (search/filter/sort): supports ?q= (SKU or title substring),
    ?min_confidence=/?max_confidence=, ?status=, and ?sort=confidence_asc /
    confidence_desc, in addition to the existing status filter links.
    """
    stats = ProductClassification.objects.aggregate(
        total=Count("id"),
        auto=Count("id", filter=Q(status="auto_classified")),
        review=Count("id", filter=Q(status="needs_review")),
        approved=Count("id", filter=Q(status="approved")),
        failed=Count("id", filter=Q(status="failed")),
    )
    status_filter = request.GET.get("status")
    query = request.GET.get("q", "").strip()
    min_confidence = request.GET.get("min_confidence", "").strip()
    max_confidence = request.GET.get("max_confidence", "").strip()
    sort = request.GET.get("sort", "")

    qs = ProductClassification.objects.select_related("product", "predicted_category").prefetch_related(
        "attribute_values__attribute", "attribute_values__value"
    )

    if status_filter:
        qs = qs.filter(status=status_filter)
    if query:
        qs = qs.filter(Q(product__sku__icontains=query) | Q(product__title__icontains=query))
    if min_confidence.isdigit():
        qs = qs.filter(confidence__gte=int(min_confidence))
    if max_confidence.isdigit():
        qs = qs.filter(confidence__lte=int(max_confidence))

    if sort == "confidence_asc":
        qs = qs.order_by("confidence", "id")
    elif sort == "confidence_desc":
        qs = qs.order_by("-confidence", "id")
    else:
        qs = qs.order_by("id")

    all_category_paths = list(Category.objects.order_by("full_path").values_list("full_path", flat=True))

    products = []
    for c in qs[:200]:
        source_label = c.product.source_sub_category or c.product.source_category
        predicted_label = c.predicted_category.name if c.predicted_category else None
        agrees = bool(
            source_label and predicted_label and
            (predicted_label.lower() in source_label.lower() or source_label.lower() in predicted_label.lower())
        )
        products.append({"c": c, "source_label": source_label, "agrees": agrees})

    return render(request, "dashboard.html", {
        "stats": stats, "products": products, "status_filter": status_filter,
        "all_category_paths": all_category_paths,
        "query": query, "min_confidence": min_confidence, "max_confidence": max_confidence, "sort": sort,
    })
