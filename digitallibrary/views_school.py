from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from .models import SchoolSetting

@staff_member_required
def school_settings_view(request):
    """Custom view to update school settings"""
    setting = SchoolSetting.objects.first()
    if not setting:
        setting = SchoolSetting()
    
    if request.method == 'POST':
        setting.name = request.POST.get('name', '')
        setting.motto = request.POST.get('motto', '')
        setting.phone = request.POST.get('phone', '')
        setting.email = request.POST.get('email', '')
        setting.address = request.POST.get('address', '')
        setting.save()
        messages.success(request, 'School settings updated successfully!')
        return redirect('digitallibrary:school_settings')
    
    return render(request, 'digitallibrary/school_settings.html', {'setting': setting})