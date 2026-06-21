@super_admin_required
def tenant_delete(request, tenant_id):
    """
    Delete a tenant completely from the public superadmin area.

    Safe deletion order:
    1. Read tenant details from public schema
    2. Delete domains from public schema
    3. Delete the School row from public schema using raw SQL
       to avoid tenant model delete hooks touching broken tenant tables
    4. Drop the tenant PostgreSQL schema

    This avoids errors such as:
        relation "digitallibrary_gradingsystem" does not exist
        relation "digitallibrary_resource" does not exist
    """
    connection.set_schema_to_public()
    request.tenant_schema = "public"

    if hasattr(request, "session"):
        request.session["tenant_schema"] = "public"
        request.session.modified = True

    with schema_context("public"):
        tenant = get_object_or_404(
            School,
            id=tenant_id,
        )

        tenant_name = tenant.name
        schema_name = tenant.schema_name
        tenant_pk = tenant.pk

        if schema_name in ["public", "", None]:
            messages.error(
                request,
                "Cannot delete the public schema.",
            )
            return redirect("/tenants/super-admin/")

        if request.method == "POST":
            try:
                connection.set_schema_to_public()

                # ------------------------------------------------------------
                # 1. Delete domains from public schema
                # ------------------------------------------------------------
                Domain.objects.filter(
                    tenant_id=tenant_pk,
                ).delete()

                # ------------------------------------------------------------
                # 2. Delete the public School row safely
                #    Use raw SQL to avoid django-tenants/model hooks trying
                #    to inspect broken tenant tables.
                # ------------------------------------------------------------
                school_table = School._meta.db_table

                with connection.cursor() as cursor:
                    cursor.execute(
                        f'DELETE FROM "{school_table}" WHERE id = %s;',
                        [tenant_pk],
                    )

                # ------------------------------------------------------------
                # 3. Drop the tenant schema after public records are removed
                # ------------------------------------------------------------
                with connection.cursor() as cursor:
                    cursor.execute(
                        f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE;'
                    )

                connection.set_schema_to_public()
                request.tenant_schema = "public"

                if hasattr(request, "session"):
                    request.session["tenant_schema"] = "public"
                    request.session.modified = True

                messages.success(
                    request,
                    (
                        f"✅ Tenant '{tenant_name}' and schema "
                        f"'{schema_name}' have been deleted successfully."
                    ),
                )

                return redirect("/tenants/super-admin/")

            except Exception as error:
                connection.set_schema_to_public()
                request.tenant_schema = "public"

                if hasattr(request, "session"):
                    request.session["tenant_schema"] = "public"
                    request.session.modified = True

                logger.error(
                    (
                        f"Error deleting tenant '{tenant_name}' "
                        f"with schema '{schema_name}': {error}"
                    )
                )

                messages.error(
                    request,
                    f"Error deleting tenant '{tenant_name}': {error}",
                )

                return redirect("/tenants/super-admin/")

        context = {
            "tenant": tenant,
            "tenant_schema": "public",
            "current_tenant_schema": "public",
            "tenant_base_url": "/tenants/super-admin",
            "tenant_dashboard_url": "/tenants/super-admin/",
            "is_super_admin_page": True,
            "is_public_schema": True,
        }

        return render(
            request,
            "tenants/tenant_delete_confirm.html",
            context,
        )
