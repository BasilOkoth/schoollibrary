# digitallibrary/management/commands/init_cbe_grades.py

from django.core.management.base import BaseCommand
from digitallibrary.models import KNECCBEGrade

class Command(BaseCommand):
    help = 'Initialize KNEC CBE grading system'

    def handle(self, *args, **options):
        KNECCBEGrade.initialize_default_grades()
        self.stdout.write(self.style.SUCCESS('Successfully initialized KNEC CBE grading system'))