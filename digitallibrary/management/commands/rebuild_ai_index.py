from django.core.management.base import BaseCommand
from digitallibrary.ai_engine import build_index_from_db

class Command(BaseCommand):
    help = "Rebuild AI search index from PDF resources"

    def handle(self, *args, **options):
        stats = build_index_from_db()
        self.stdout.write(self.style.SUCCESS(
            f"Index rebuild complete. PDFs found: {stats['pdfs']} | Chunks indexed: {stats['chunks']}"
        ))