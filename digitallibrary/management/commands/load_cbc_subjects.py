# digitallibrary/management/commands/load_cbc_subjects.py
from django.core.management.base import BaseCommand
from digitallibrary.models import Subject

class Command(BaseCommand):
    help = 'Load CBC Senior School subjects into the database'

    def handle(self, *args, **options):
        # Compulsory Subjects (All students must take these)
        compulsory_subjects = [
            "English",
            "Kiswahili/KSL",
            "Core Mathematics",
            "Essential Mathematics",
            "Community Service Learning (CSL)",
        ]
        
        # Arts & Sports Science Pathway Subjects
        arts_sports_subjects = [
            "Sports and Recreation",
            "Music and Dance",
            "Theatre and Film",
            "Fine Arts",
        ]
        
        # Social Sciences Pathway Subjects
        social_sciences_subjects = [
            "Literature in English",
            "Indigenous Languages",
            "Fasihi ya Kiswahili",
            "Sign Language",
            "Arabic",
            "French",
            "German",
            "Mandarin Chinese",
            "Christian Religious Education",
            "Islamic Religious Education",
            "Hindu Religious Education",
            "Business Studies",
            "History and Citizenship",
            "Geography",
        ]
        
        # STEM Pathway Subjects
        stem_subjects = [
            "Biology",
            "Chemistry",
            "Physics",
            "General Science",
            "Agriculture",
            "Computer Studies",
            "Home Science",
            "Aviation",
            "Building Construction",
            "Electricity",
            "Metalwork",
            "Power Mechanics",
            "Woodwork",
            "Media Technology",
            "Marine and Fisheries Technology",
        ]
        
        # Create subjects with their categories
        subjects_data = [
            (compulsory_subjects, 'compulsory', True),
            (arts_sports_subjects, 'arts_sports', False),
            (social_sciences_subjects, 'social_sciences', False),
            (stem_subjects, 'stem', False),
        ]
        
        count = 0
        for subjects_list, category, is_compulsory in subjects_data:
            for idx, subject_name in enumerate(subjects_list, 1):
                obj, created = Subject.objects.get_or_create(
                    name=subject_name,
                    defaults={
                        'category': category,
                        'is_compulsory': is_compulsory,
                        'order': idx,
                        'is_active': True
                    }
                )
                if created:
                    count += 1
                    self.stdout.write(f"Created: {subject_name} - {category}")
                else:
                    # Update existing subjects
                    obj.category = category
                    obj.is_compulsory = is_compulsory
                    obj.order = idx
                    obj.save()
                    self.stdout.write(f"Updated: {subject_name} - {category}")
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully loaded {count} new CBC subjects. Total subjects: {Subject.objects.count()}')
        )