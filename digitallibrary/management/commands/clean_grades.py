from django.core.management.base import BaseCommand
from digitallibrary.models import Resource

class Command(BaseCommand):
    help = 'Clean and standardize grade values in resources'

    def handle(self, *args, **options):
        grade_mapping = {
            # Form 1 variations
            'form1': 'Form 1',
            'form 1': 'Form 1',
            'Form1': 'Form 1',
            'FORM1': 'Form 1',
            'FORM 1': 'Form 1',
            'form i': 'Form 1',
            'form one': 'Form 1',
            '1': 'Form 1',
            
            # Form 2 variations
            'form2': 'Form 2',
            'form 2': 'Form 2',
            'Form2': 'Form 2',
            'FORM2': 'Form 2',
            'FORM 2': 'Form 2',
            'form ii': 'Form 2',
            'form two': 'Form 2',
            '2': 'Form 2',
            
            # Form 3 variations
            'form3': 'Form 3',
            'form 3': 'Form 3',
            'Form3': 'Form 3',
            'FORM3': 'Form 3',
            'FORM 3': 'Form 3',
            'form iii': 'Form 3',
            'form three': 'Form 3',
            '3': 'Form 3',
            
            # Form 4 variations
            'form4': 'Form 4',
            'form 4': 'Form 4',
            'Form4': 'Form 4',
            'FORM4': 'Form 4',
            'FORM 4': 'Form 4',
            'form iv': 'Form 4',
            'form four': 'Form 4',
            '4': 'Form 4',
            
            # General variations
            'general': 'General',
            'General': 'General',
            'GENERAL': 'General',
            'all': 'General',
            'All': 'General',
            'ALL': 'General',
            '': 'General',
            None: 'General',
        }
        
        updated_count = 0
        resources = Resource.objects.all()
        
        for resource in resources:
            old_grade = resource.grade
            grade_lower = str(old_grade).lower().strip() if old_grade else ''
            
            if grade_lower in grade_mapping:
                new_grade = grade_mapping[grade_lower]
                if old_grade != new_grade:
                    resource.grade = new_grade
                    resource.save()
                    updated_count += 1
                    self.stdout.write(f"Updated: '{old_grade}' -> '{new_grade}'")
        
        self.stdout.write(self.style.SUCCESS(f"\n✅ Updated {updated_count} resources"))
        
        # Show final grade distribution
        from django.db.models import Count
        grade_dist = Resource.objects.values('grade').annotate(count=Count('id')).order_by('grade')
        self.stdout.write("\n📊 Final grade distribution:")
        for g in grade_dist:
            self.stdout.write(f"  {g['grade']}: {g['count']} resources")