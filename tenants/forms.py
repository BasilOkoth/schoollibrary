from django import forms
from .models import School, Domain

class TenantCreationForm(forms.Form):
    school_name = forms.CharField(
        max_length=255, 
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    schema_name = forms.CharField(
        max_length=100, 
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    domain = forms.CharField(
        max_length=255, 
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    principal_email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    administrator_email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )


class TenantUpdateForm(forms.ModelForm):
    class Meta:
        model = School
        # Use 'phone_number' not 'phone'
        fields = ['name', 'address', 'phone_number', 'email']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }


class ResetPasswordForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}), 
        min_length=8
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password and new_password != confirm_password:
            raise forms.ValidationError("Passwords do not match")
        return cleaned_data