# fix_miyuga_fees.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoollibrary.settings')
django.setup()

from tenants.models import School
from django_tenants.utils import tenant_context
from decimal import Decimal

def fix_miyuga_fees():
    print("=" * 60)
    print("Fixing Miyuga School Fees")
    print("=" * 60)
    
    miyuga = School.objects.get(schema_name='miyuga')
    
    with tenant_context(miyuga):
        from digitallibrary.models import FeeBalance, Student, FeeStructure
        from django.db.models import Sum
        
        current_year = '2026'
        current_term = 1
        
        # Delete existing fee balances
        deleted = FeeBalance.objects.all().delete()
        print(f"Deleted {deleted[0]} existing fee balances")
        
        # Get all active students
        students = Student.objects.filter(is_active=True)
        print(f"\nActive students: {students.count()}")
        print("-" * 40)
        
        created = 0
        total_expected = Decimal('0')
        total_paid = Decimal('0')
        
        for student in students:
            # Get fee structure for this student's class
            fee_structure = FeeStructure.objects.filter(
                student_class=student.current_class,
                academic_year=current_year,
                term=current_term
            ).first()
            
            if fee_structure:
                # Calculate total paid for this student
                paid = student.payments.filter(
                    academic_year=current_year,
                    term=current_term
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
                
                expected = fee_structure.total_fees
                balance = expected - paid
                
                # Determine status
                if balance == 0:
                    status = 'PAID'
                elif paid > 0:
                    status = 'PARTIAL'
                else:
                    status = 'DEFAULTING'
                
                # Create fee balance
                FeeBalance.objects.create(
                    student=student,
                    term=current_term,
                    academic_year=current_year,
                    total_expected=expected,
                    total_paid=paid,
                    balance=balance,
                    status=status
                )
                
                created += 1
                total_expected += expected
                total_paid += paid
                
                emoji = "✅" if status == 'PAID' else "🟡" if status == 'PARTIAL' else "🔴"
                print(f"{emoji} {student.get_full_name()[:25]:25} | {status}")
            else:
                print(f"⚠️ {student.get_full_name()[:25]:25} | NO FEE STRUCTURE")
        
        # Print summary
        print("\n" + "=" * 60)
        print("SUMMARY FOR MIYUGA SCHOOL")
        print("=" * 60)
        print(f"Fee balances created: {created}")
        print(f"Total Expected Fees: KES {total_expected:,.2f}")
        print(f"Total Paid:          KES {total_paid:,.2f}")
        print(f"Total Balance:       KES {total_expected - total_paid:,.2f}")
        
        # Count by status
        paid_count = FeeBalance.objects.filter(status='PAID').count()
        partial_count = FeeBalance.objects.filter(status='PARTIAL').count()
        defaulting_count = FeeBalance.objects.filter(status='DEFAULTING').count()
        
        print(f"\nStatus Breakdown:")
        print(f"  ✅ Fully Paid:    {paid_count} students")
        print(f"  🟡 Partially Paid: {partial_count} students")
        print(f"  🔴 Defaulting:    {defaulting_count} students")
        
        print("\n✅ Done! Refresh your fees dashboard.")

if __name__ == "__main__":
    fix_miyuga_fees()
    
    # This will pause the script on Windows
    print("\n" + "=" * 60)
    print("Script completed. Press ENTER to close this window...")
    try:
        input()
    except:
        pass