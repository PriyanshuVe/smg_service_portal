from django.contrib import admin

# Register your models here.
from .models import Dealer, LabourService, ServiceRecord
from .models import Component
from .models import Inventory
admin.site.register(Inventory)

@admin.register(LabourService)
class LabourServiceAdmin(admin.ModelAdmin):
    list_display = ('job_code', 'description', 'cost')
    search_fields = ('job_code', 'description')

@admin.register(Dealer)
class DealerAdmin(admin.ModelAdmin):
    list_display = ('dealer_id','name','email','contact','city','state')
    search_fields = ('dealer_id','name','email')

@admin.register(ServiceRecord)
class ServiceRecordAdmin(admin.ModelAdmin):
    list_display = ('id','dealer','customer_name','customer_phone','total_cost','created_at')
    list_filter = ('dealer', 'created_at')
    search_fields = ('customer_name','customer_phone')
    
@admin.register(Component)
class ComponentAdmin(admin.ModelAdmin):
    list_display = ('part_code', 'part_name', 'price')
    search_fields = ('part_code', 'part_name')
