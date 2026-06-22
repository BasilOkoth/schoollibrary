from django import forms

from .models import School, SCHOOL_LEVEL_CHOICES


class TenantCreationForm(forms.Form):
    school_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. Nyandago Secondary School",
            }
        ),
        label="School Name",
    )

    schema_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. nyandago",
            }
        ),
        label="Tenant Schema Name",
        help_text=(
            "Use a short name such as nyandago. Spaces and hyphens "
            "will be converted to underscores."
        ),
    )

    school_level = forms.ChoiceField(
        choices=SCHOOL_LEVEL_CHOICES,
        initial="CBC_LEGACY_SECONDARY",
        widget=forms.Select(
            attrs={
                "class": "form-control",
            }
        ),
        label="School Level",
        help_text="Select the school structure for this tenant.",
    )

    principal_email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "principal@example.com",
            }
        ),
        label="Principal Email",
    )

    administrator_email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "admin@example.com",
            }
        ),
        label="Administrator Email",
    )

    def clean_schema_name(self):
        schema_name = self.cleaned_data.get("schema_name", "")

        schema_name = (
            schema_name
            .lower()
            .strip()
            .replace(" ", "_")
            .replace("-", "_")
        )

        # PostgreSQL schema names should not start with a number
        if not schema_name:
            raise forms.ValidationError("Schema name is required.")

        if schema_name[0].isdigit():
            raise forms.ValidationError(
                "Schema name cannot start with a number."
            )

        # Allow only lowercase letters, numbers and underscores
        for character in schema_name:
            if not (
                character.islower()
                or character.isdigit()
                or character == "_"
            ):
                raise forms.ValidationError(
                    (
                        "Schema name can only contain lowercase letters, "
                        "numbers, and underscores."
                    )
                )

        reserved_names = {
            "public",
            "admin",
            "login",
            "logout",
            "static",
            "media",
            "tenant",
            "tenants",
            "superadmin",
            "super_admin",
            "super-admin",
            "secure_admin",
            "secure-admin",
            "app",
            "library",
            "mpesa",
        }

        if schema_name in reserved_names:
            raise forms.ValidationError(
                (
                    f"'{schema_name}' is reserved and cannot be used "
                    "as a tenant schema."
                )
            )

        if School.objects.filter(schema_name=schema_name).exists():
            raise forms.ValidationError(
                f"A tenant with schema '{schema_name}' already exists."
            )

        return schema_name

    def clean(self):
        cleaned_data = super().clean()

        principal_email = cleaned_data.get("principal_email")
        administrator_email = cleaned_data.get("administrator_email")

        if (
            principal_email
            and administrator_email
            and principal_email.lower() == administrator_email.lower()
        ):
            raise forms.ValidationError(
                "Principal email and administrator email should be different."
            )

        return cleaned_data


class TenantUpdateForm(forms.ModelForm):
    class Meta:
        model = School
        fields = [
            "name",
            "address",
            "phone_number",
            "email",
            "school_level",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                }
            ),
            "phone_number": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "school_level": forms.Select(
                attrs={"class": "form-control"}
            ),
        }


class ResetPasswordForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Username",
            }
        )
    )

    new_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "New password",
            }
        ),
        min_length=8,
    )

    confirm_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Confirm password",
            }
        )
    )

    def clean(self):
        cleaned_data = super().clean()

        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        if (
            new_password
            and confirm_password
            and new_password != confirm_password
        ):
            raise forms.ValidationError("Passwords do not match.")

        return cleaned_data
