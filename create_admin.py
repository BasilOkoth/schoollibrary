import os 
import django 
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoollibrary.settings') 
django.setup() 
from django.contrib.auth.models import User 
from django_tenants.utils import tenant_context 
from tenants.models import Tenant 
print("\n=== AVAILABLE TENANTS ===") 
for t in Tenant.objects.all(): 
    print("  Schema: " + t.schema_name + " | Name: " + t.name) 
try: 
    tenant = Tenant.objects.get(schema_name='orero_school') 
    print("\nû Found tenant: " + tenant.name) 
    with tenant_context(tenant): 
        if not User.objects.filter(username='admin').exists(): 
            User.objects.create_superuser('admin', 'admin@orero.com', 'Orero2024!') 
            print("û Created superuser 'admin'") 
        else: 
            print("û Superuser 'admin' already exists") 
    print("\n? SUCCESS!") 
    print("Login: http://localhost:8000/?tenant=orero_school/admin/") 
    print("Username: admin") 
    print("Password: Orero2024!") 
except Exception as e: 
    print("\n? Error: " + str(e)) 
