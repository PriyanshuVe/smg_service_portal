"""
URL configuration for smg_portal project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from portal import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='index'),
    # path('admin-login/', views.admin_login, name='admin_login'),
    # path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('portal-admin/login/', views.admin_login, name='admin_login'),
    path('portal-admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('dealer-login/', views.dealer_login, name='dealer_login'),
    path('dealer-dashboard/', views.dealer_dashboard, name='dealer_dashboard'),
    path('bill/<int:record_id>/', views.bill_view, name='bill_view'),
    path('admin-manage-rates/', views.admin_manage_rates, name='admin_manage_rates'),
    path('bill/<int:record_id>/download/', views.download_bill_pdf, name='download_bill_pdf'),
    path('dealer/add_inventory/', views.dealer_add_inventory, name='dealer_add_inventory'),
    path('dealer/inventory/delete/<int:item_id>/', views.delete_inventory, name='delete_inventory'),
    # if using smg_portal/urls.py and imported views as from portal import views
    path('admin-manage-labour-components/', views.admin_manage_labour_components, name='admin_manage_labour_components'),
    # path('admin/dealer/edit/<int:dealer_id>/', views.edit_dealer, name='edit_dealer'),
    # path('admin/dealer/delete/<int:dealer_id>/', views.delete_dealer, name='delete_dealer'),
    path('portal-admin/dealer/edit/<int:dealer_id>/', views.edit_dealer, name='edit_dealer'),
    path('portal-admin/dealer/delete/<int:dealer_id>/', views.delete_dealer, name='delete_dealer'),
    path('test-ride/', views.test_ride_form, name='test_ride_form'),
    path('customer-feedback/', views.customer_feedback_form, name='customer_feedback_form'),
    # Quotation Maker
    path('dealer/quotation/', views.dealer_quotation, name='dealer_quotation'),
    path('dealer/quotation/download/<int:quotation_id>/', views.download_quotation_excel, name='download_quotation_excel'),
    path('pdi-inspection/', views.pdi_inspection_form, name='pdi_inspection_form'),
    path('pdi-list/', views.pdi_list, name='pdi_list'),
    path('my-service-records/', views.my_service_records, name='my_service_records'),
    path('technicians/', views.technician_list, name='technician_list'),
    path('technicians/delete/<int:id>/', views.delete_technician, name='delete_technician'),
    path('technicians/edit/<int:id>/', views.edit_technician, name='edit_technician'),
    # Dealer to Dealer Sale
    path('dealer-sale/', views.dealer_sale_list, name='dealer_sale_list'),
    path('dealer-sale/add/', views.dealer_sale_add, name='dealer_sale_add'),
    path('dealer-sale/delete/<int:id>/', views.delete_dealer_sale, name='delete_dealer_sale'),
    path('dealer-sale/export/', views.export_sales_excel, name='export_sales_excel'),
    # Dealer to Dealer Purchase
    path('dealer-purchase/', views.dealer_purchase_list, name='dealer_purchase_list'),
    path('dealer-purchase/add/', views.dealer_purchase_add, name='dealer_purchase_add'),
    path('dealer-purchase/delete/<int:id>/', views.delete_dealer_purchase, name='delete_dealer_purchase'),
    path('dealer-purchase/export/', views.export_purchases_excel, name='export_purchases_excel'),
    path('warranty/', views.warranty_home, name='warranty_home'),
    path('warranty/failed-tag/', views.failed_tag_form, name='failed_tag_form'),
    path('warranty/claim/', views.warranty_claim_form, name='warranty_claim_form'),
    path('warranty/pickup/', views.warranty_pickup_form, name='warranty_pickup_form'),
    path('warranty/claim/pdf/<int:pk>/', views.warranty_claim_pdf, name='warranty_claim_pdf'),
    path('warranty/pickup/pdf/<int:pk>/', views.warranty_pickup_pdf, name='warranty_pickup_pdf'),
    path('quotation/<int:quotation_id>/pdf/', views.quotation_pdf, name='quotation_pdf'),
]

