from django.contrib.auth.views import (
    PasswordResetView,
    PasswordResetConfirmView,
)


class TenantPasswordResetView(PasswordResetView):
    template_name = "digitallibrary/password_reset.html"
    email_template_name = "digitallibrary/password_reset_email.html"
    subject_template_name = "digitallibrary/password_reset_subject.txt"

    def dispatch(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)

        self.extra_email_context = {
            "tenant_schema": getattr(tenant, "schema_name", "public"),
        }

        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        schema_name = self.request.tenant.schema_name

        return (
            f"/tenant/{schema_name}/app/"
            "password-reset/done/"
        )


class TenantPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "digitallibrary/password_reset_confirm.html"

    def get_success_url(self):
        schema_name = self.request.tenant.schema_name

        return (
            f"/tenant/{schema_name}/app/"
            "password-reset/complete/"
        )
