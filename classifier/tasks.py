"""
Real Celery tasks for distributed batch classification (README Priority 7).

Unlike the sync path in classify_catalogue.py (one Python process looping
over chunks), this dispatches one task per product to however many Celery
workers you run, which is what actually lets 10,000+ products be processed
concurrently instead of sequentially (Q4, Q10).

HONESTY NOTE: this code is written to run correctly against a real
Celery + Redis setup, and follows standard, well-documented Celery
patterns -- but it has not been executed in the sandbox this project was
built in (no internet access there to install Celery or run Redis). Unlike
the vision/LLM layers (blocked by needing a paid API key), this is only
blocked by sandbox tooling, not by anything you can't also do -- you have
full internet access, so you can actually install Redis + Celery and test
this for real. See README "Priority 7" for the exact steps.

Usage:
    # Terminal 1: run Redis (simplest via Docker)
    docker run -p 6379:6379 redis

    # Terminal 2: run a worker
    celery -A config worker --loglevel=info --pool=solo   # --pool=solo required on Windows

    # Terminal 3: dispatch work
    python manage.py classify_catalogue "Product List.xlsx" --limit 5000 --async
"""

from celery import shared_task
from django.utils import timezone


@shared_task(bind=True, max_retries=3, acks_late=True)
def classify_one_product(self, classification_id, job_id, with_images, with_vision, with_llm):
    """
    Classifies exactly one product. One task per product (rather than one
    task per chunk) is deliberate for the scenario in Q10 -- if each
    external image/LLM call takes ~2 seconds, a single slow call must never
    block the other 99 products in its chunk; each product's fate is fully
    independent.

    acks_late=True means this task is only marked complete by the broker
    after it actually finishes. If the worker process crashes mid-task, the
    broker redelivers it to another worker automatically -- this is the
    resumability mechanism for the Celery path (Q11), complementing the
    per-row `status` field which is the resumability mechanism for the sync
    path.
    """
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
    """
    Alternative entry point: fan out all currently-pending classifications
    for a job as individual tasks. classify_catalogue.py's --async flag
    calls .delay() per product directly instead of using this, but this task
    is provided so dispatch can itself be queued (useful if you want the
    Django view/command to return instantly and let a worker do the fan-out).
    """
    from classifier.models import ProductClassification

    pending_ids = ProductClassification.objects.filter(
        job_id=job_id, status__in=["pending", "processing"]
    ).values_list("id", flat=True)

    for classification_id in pending_ids:
        classify_one_product.delay(classification_id, job_id, with_images, with_vision, with_llm)
