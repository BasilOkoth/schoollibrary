def tenant_context(request):
    """
    Makes tenant information available globally to templates.
    """

    host = request.get_host().split(':')[0].lower()

    is_public_domain = host in [
        'shulehub.org',
        'www.shulehub.org',
        'schoollibrary.onrender.com',
        'schoollibrary-1.onrender.com'
    ]

    schema_name = 'public'
    tenant_name = 'Public'

    if hasattr(request, 'tenant') and request.tenant:
        schema_name = request.tenant.schema_name
        tenant_name = getattr(request.tenant, 'name', schema_name)

    is_public = (
        schema_name == 'public'
        or is_public_domain
    )

    # Build tenant-aware URL prefixes
    if not is_public and schema_name:
        app_prefix = f"/tenant/{schema_name}/app"
        tenant_url_prefix = f"/tenant/{schema_name}"
    else:
        app_prefix = "/app"
        tenant_url_prefix = ""

    return {
        # Tenant info
        'tenant_schema': schema_name,
        'tenant_name': tenant_name,

        # Flags
        'is_public_schema': is_public,
        'is_tenant_schema': not is_public,

        # Host info
        'current_host': host,
        'current_schema': schema_name,

        # URL helpers
        'app_prefix': app_prefix,
        'tenant_url_prefix': tenant_url_prefix,
    }
