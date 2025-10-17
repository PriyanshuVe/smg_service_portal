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
    path('admin-login/', views.admin_login, name='admin_login'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('dealer-login/', views.dealer_login, name='dealer_login'),
    path('dealer-dashboard/', views.dealer_dashboard, name='dealer_dashboard'),
    path('bill/<int:record_id>/', views.bill_view, name='bill_view'),
    path('admin-manage-rates/', views.admin_manage_rates, name='admin_manage_rates'),
    path('bill/<int:record_id>/download/', views.download_bill_pdf, name='download_bill_pdf'),
    path('dealer/add_inventory/', views.dealer_add_inventory, name='dealer_add_inventory'),
    # if using smg_portal/urls.py and imported views as from portal import views
    path('admin-manage-labour-components/', views.admin_manage_labour_components, name='admin_manage_labour_components'),
]

