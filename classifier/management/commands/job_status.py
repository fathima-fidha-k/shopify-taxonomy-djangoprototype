"""
Usage: python manage.py job_status <job_id>

Prints progress for a batch job -- most useful when running with --async,
since Celery workers process in the background and there's no live console
output like the sync command has.
"""

from django.core.management.base import BaseCommand, CommandError
from classifier.models import ClassificationJob


class Command(BaseCommand):
    help = "Check progress of a classification job (useful for --async / Celery runs)."

    def add_arguments(self, parser):
        parser.add_argument("job_id", type=int)

    def handle(self, *args, **options):
        try:
            job = ClassificationJob.objects.get(id=options["job_id"])
        except ClassificationJob.DoesNotExist:
            raise CommandError(f"No job with id {options['job_id']}")

        remaining = job.total - job.done - job.failed - job.needs_review
        self.stdout.write(f"Job #{job.id} (mode={job.mode}, started={job.started_at})")
        self.stdout.write(f"  total:        {job.total}")
        self.stdout.write(f"  auto:         {job.done}")
        self.stdout.write(f"  needs review: {job.needs_review}")
        self.stdout.write(f"  failed:       {job.failed}")
        self.stdout.write(f"  remaining:    {max(0, remaining)}")
        self.stdout.write(f"  finished:     {job.finished_at or 'not yet'}")
