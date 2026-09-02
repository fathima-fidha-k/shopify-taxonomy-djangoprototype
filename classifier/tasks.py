from celery import shared_task
from django.utils import timezone


@shared_task(bind=True, max_retries=3, acks_late=True)
def classify_one_product(self, classification_id, job_id, with_images, with_vision, with_llm):
    # Imported inside the task, not at module load time, so that importing
    # this module never fails just because Django hasn't finished setting up
    # yet when Celery first discovers tasks.
    from classifier.models import Product, ProductClassification, ClassificationJob, Category, Attribute
    from classifier.services.engine import classify_product
    from classifier.services.image_analysis import analyze_image
    from classifier.management.commands.classify_catalogue import Command as ClassifyCommand

    try:
        classification = ProductClassification.objects.select_related("product").get(id=classification_id)
    except ProductClassification.DoesNotExist:
        return  # product was deleted since dispatch -- nothing to do

    if classification.status not in ("pending", "processing"):
        return  # already handled (e.g. a redelivered duplicate task) -- don't reclassify

    classification.status = "processing"
    classification.save(update_fields=["status"])

    try:
        product = classification.product
        job = ClassificationJob.objects.filter(id=job_id).first()

        image_result = None
        if with_images and product.image_url:
            image_result = analyze_image(product.image_url)

        result = classify_product(
            {
                "title": product.title, "description": product.description,
                "product_type": product.product_type, "brand": product.brand,
                "image_url": product.image_url,
            },
            use_llm=with_llm, use_vision=with_vision, image_result=image_result,
        )  # never raises internally -- see services/engine.py

        categories_by_path = {c.full_path: c for c in Category.objects.all()}
        attributes_by_name = {a.name.lower(): a for a in Attribute.objects.all()}
        ClassifyCommand._apply_result(classification, result, job, categories_by_path, attributes_by_name)

        if job:
            _update_job_counters(job)

    except Exception as exc:
        # A genuinely unexpected error (not one already caught inside
        # classify_product, which never raises) -- retry with backoff rather
        # than immediately marking the whole product failed, since this is
        # more likely a transient issue (DB contention, etc.) than a bad
        # product.
        classification.status = "pending"  # so a restart/resume pass will retry it (Q11)
        classification.save(update_fields=["status"])
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


def _update_job_counters(job):
    """Recompute a job's progress counters from its classifications. Safe to
    call concurrently from many workers since it's a pure read+write of
    aggregate counts, not a per-row mutation."""
    from classifier.models import ProductClassification
    from django.db.models import Count, Q

    counts = ProductClassification.objects.filter(job=job).aggregate(
        done=Count("id", filter=Q(status="auto_classified")),
        failed=Count("id", filter=Q(status="failed")),
        needs_review=Count("id", filter=Q(status="needs_review")),
        remaining=Count("id", filter=Q(status__in=["pending", "processing"])),
    )
    job.done = counts["done"]
    job.failed = counts["failed"]
    job.needs_review = counts["needs_review"]
    if counts["remaining"] == 0 and not job.finished_at:
        job.finished_at = timezone.now()
    job.save(update_fields=["done", "failed", "needs_review", "finished_at"])


@shared_task
def dispatch_pending_classifications(job_id, with_images, with_vision, with_llm):
    from classifier.models import ProductClassification

    pending_ids = ProductClassification.objects.filter(
        job_id=job_id, status__in=["pending", "processing"]
    ).values_list("id", flat=True)

    for classification_id in pending_ids:
        classify_one_product.delay(classification_id, job_id, with_images, with_vision, with_llm)
