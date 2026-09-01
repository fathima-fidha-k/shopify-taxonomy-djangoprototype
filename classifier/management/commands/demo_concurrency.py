"""
Usage: python manage.py demo_concurrency [--count 50] [--latency 2.0] [--workers 20]

Concretely demonstrates the scenario in the assignment's Q10: "if the
application needs to process 10,000 products and each external AI/API
request takes approximately 2 seconds, how would you optimize the
processing time?"

Rather than just asserting the math in the written answer, this actually
runs a small number of *simulated* external calls (a real `time.sleep`, not
a mock that returns instantly) both sequentially and concurrently, measures
real wall-clock time for both, and then extrapolates to the full 10,000/2s
scenario using the measured concurrent-vs-sequential ratio from your own
machine -- not a made-up theoretical number.

Defaults to a small --count and short --latency so it runs in seconds, not
hours, while still proving the concept with real measured timings. Bump
--count and --latency up if you want to see it closer to the real scenario
(e.g. --count 200 --latency 2.0 --workers 20 takes about 20 seconds
concurrently vs. ~6.7 minutes sequentially).
"""

import time
from concurrent.futures import ThreadPoolExecutor

from django.core.management.base import BaseCommand


def fake_external_api_call(latency_seconds):
    """Stands in for a real external AI/vision API call -- a genuine
    time.sleep, not a mock, so the measured timings below are real."""
    time.sleep(latency_seconds)
    return True


class Command(BaseCommand):
    help = "Concretely demonstrates sequential vs. concurrent processing time for the Q10 scenario."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=50, help="Number of simulated products (default 50)")
        parser.add_argument("--latency", type=float, default=0.5, help="Simulated per-call latency in seconds (default 0.5; the assignment's scenario uses 2.0)")
        parser.add_argument("--workers", type=int, default=20, help="Number of concurrent workers (default 20)")

    def handle(self, *args, **options):
        count = options["count"]
        latency = options["latency"]
        workers = options["workers"]

        self.stdout.write(f"Simulating {count} products, {latency}s per external call, {workers} concurrent workers.\n")

        # -- Sequential --
        self.stdout.write("Running sequentially...")
        t0 = time.time()
        for _ in range(count):
            fake_external_api_call(latency)
        sequential_time = time.time() - t0
        self.stdout.write(f"  Sequential: {sequential_time:.2f}s\n")

        # -- Concurrent (thread pool -- same concept as N Celery workers pulling from one queue) --
        self.stdout.write(f"Running concurrently ({workers} workers)...")
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=workers) as executor:
            list(executor.map(lambda _: fake_external_api_call(latency), range(count)))
        concurrent_time = time.time() - t0
        self.stdout.write(f"  Concurrent: {concurrent_time:.2f}s\n")

        speedup = sequential_time / concurrent_time if concurrent_time else float("inf")
        self.stdout.write(self.style.SUCCESS(f"Measured speedup: {speedup:.1f}x\n"))

        # -- Extrapolate to the assignment's actual scenario using the measured ratio --
        real_count, real_latency = 10000, 2.0
        real_sequential_hours = (real_count * real_latency) / 3600
        real_concurrent_estimate_minutes = (real_sequential_hours * 3600 / speedup) / 60

        self.stdout.write("Extrapolating to the assignment's actual scenario (10,000 products, 2s/call):")
        self.stdout.write(f"  Sequential (no concurrency):  {real_sequential_hours:.2f} hours")
        self.stdout.write(
            f"  Concurrent (using this machine's measured {speedup:.1f}x speedup "
            f"from {workers} workers): ~{real_concurrent_estimate_minutes:.1f} minutes"
        )
        self.stdout.write(
            "\nNote: this is a thread-pool simulation of concurrency, not a live Celery+Redis run "
            "(see README Priority 7 for that) -- but it demonstrates the real, measured effect of "
            "concurrency on wall-clock time using this exact machine, not just a theoretical claim."
        )
