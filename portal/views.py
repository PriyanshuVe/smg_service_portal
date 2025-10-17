from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Dealer, ServiceRecord, LabourService, Component, Inventory, VehicleModel
from .models import Component
from django.utils import timezone
from django.contrib import messages
from decimal import Decimal, InvalidOperation
from django.db import IntegrityError, transaction
import random, string
from django.http import HttpResponse


def is_portal_admin(request):
    """
    Returns True when user is authorized to use the custom admin pages.
    Accept either Django staff user OR custom admin session flag used by your admin-login.
    """
    if request.user.is_authenticated and request.user.is_staff:
        return True
    # if you set session flag on custom admin login, keep support:
    if request.session.get('is_admin') or request.session.get('admin_logged_in'):
        return True
    return False


def admin_manage_labour_components(request):
    # authorization
    if not is_portal_admin(request):
        messages.error(request, "You must be logged in as admin to access this page.")
        return redirect('admin_login')   # your custom admin login page name

    # fetch lists
    labour_qs = LabourService.objects.all().order_by('job_code')
    component_qs = Component.objects.all().order_by('part_code')
    models_qs = VehicleModel.objects.all().order_by('name') if 'VehicleModel' in globals() else []

    # POST handling: two main actions - bulk update, add new
    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            with transaction.atomic():
                # Bulk update existing LabourService rows
                if action == 'save_all':
                    for s in labour_qs:
                        desc = request.POST.get(f'labour_desc_{s.id}', '').strip()
                        cost = request.POST.get(f'labour_cost_{s.id}', '').strip()
                        code = request.POST.get(f'labour_code_{s.id}', '').strip()
                        # Basic validation
                        if not desc or not cost:
                            continue
                        s.description = desc
                        try:
                            s.cost = int(cost)
                        except ValueError:
                            s.cost = s.cost
                        if code:
                            s.job_code = code
                        s.save()

                    for c in component_qs:
                        part_code = request.POST.get(f'comp_code_{c.id}', '').strip()
                        part_name = request.POST.get(f'comp_name_{c.id}', '').strip()
                        price = request.POST.get(f'comp_price_{c.id}', '').strip()
                        model_id = request.POST.get(f'comp_model_{c.id}', '').strip()

                        if not part_name or not price:
                            continue

                        c.part_name = part_name

                        try:
                            c.price = Decimal(price)
                        except (InvalidOperation, ValueError):
                            messages.warning(request, f"Invalid price for {part_name}. Keeping old value.")
                            # keep old value
                            pass

                        if part_code:
                            c.part_code = part_code

                        # update model relation (optional)
                        if model_id:
                            try:
                                vm = VehicleModel.objects.get(id=int(model_id))
                                c.model = vm
                            except (VehicleModel.DoesNotExist, ValueError):
                                pass

                        c.save()

                    messages.success(request, "All changes saved successfully.")
                    return redirect('admin_manage_labour_components')

                # Add new labour entry
                if action == 'add_labour':
                    job_code = request.POST.get('new_labour_code', '').strip()
                    desc = request.POST.get('new_labour_desc', '').strip()
                    cost = request.POST.get('new_labour_cost', '').strip()
                    if not job_code or not desc or not cost:
                        messages.error(request, "Please provide job code, description and cost for new labour.")
                        return redirect('admin_manage_labour_components')
                    try:
                        cost_int = int(cost)
                    except ValueError:
                        messages.error(request, "Labour cost must be a number.")
                        return redirect('admin_manage_labour_components')

                    LabourService.objects.create(job_code=job_code, description=desc, cost=cost_int)
                    messages.success(request, f"Added Labour {job_code} successfully.")
                    return redirect('admin_manage_labour_components')

                # Add new component entry
                if action == 'add_component':
                    part_code = request.POST.get('new_comp_code', '').strip()
                    name = request.POST.get('new_comp_name', '').strip()
                    price = request.POST.get('new_comp_price', '').strip()
                    model_id = request.POST.get('new_comp_model', '').strip()

                    if not part_code or not name or not price:
                        messages.error(request, "Please provide part code, name and price for new component.")
                        return redirect('admin_manage_labour_components')

                    try:
                        price_f = Decimal(price)
                    except (InvalidOperation, ValueError):
                        messages.error(request, "Component price must be a valid decimal number.")
                        return redirect('admin_manage_labour_components')

                    comp = Component(part_code=part_code, part_name=name, price=price_f)
                    if model_id:
                        try:
                            comp.model = VehicleModel.objects.get(id=int(model_id))
                        except (VehicleModel.DoesNotExist, ValueError):
                            comp.model = None
                    try:
                        comp.save()
                    except IntegrityError:
                        messages.error(request, "Part code already exists or invalid. Use a unique part code.")
                        return redirect('admin_manage_labour_components')
                    # Optionally create dealer inventory rows? No: admin just defines component.
                    messages.success(request, f"Component {part_code} added.")
                    return redirect('admin_manage_labour_components')

                # Optional delete actions (if you want to enable)
                if action and action.startswith('delete_comp_'):
                    comp_id = action.replace('delete_comp_', '')
                    comp = get_object_or_404(Component, id=comp_id)
                    comp.delete()
                    messages.success(request, "Component deleted.")
                    return redirect('admin_manage_labour_components')

        except Exception as e:
            messages.error(request, f"Error processing request: {str(e)}")
            return redirect('admin_manage_labour_components')

    # GET: render
    context = {
        'labour_services': labour_qs,
        'components': component_qs,
        'models': models_qs,
    }
    return render(request, 'portal/admin_manage_labour_components.html', context)


# ✅ Landing Page View
def index(request):
    return render(request, 'portal/index.html')

# ✅ Admin Login View
def admin_login(request):
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_staff:
            login(request, user)
            return redirect('admin_dashboard')
        else:
            return render(request, 'portal/login.html', {'error': 'Invalid credentials'})
    return render(request, 'portal/login.html')

# ✅ Admin Dashboard View
def admin_dashboard(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')

    if request.method == "POST":
        name = request.POST['name']
        email = request.POST['email']
        contact = request.POST['contact']
        location = request.POST['location']
        city = request.POST['city']
        state = request.POST['state']

        # Fixed format dealer_id (e.g., D1001, D1002...)
        last = Dealer.objects.last()
        next_id = 1001 if not last else int(last.dealer_id[1:]) + 1
        dealer_id = f"D{next_id}"

        # Random password (for first login)
        import random, string
        password = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

        Dealer.objects.create(
            dealer_id=dealer_id,
            name=name,
            email=email,
            contact=contact,
            location=location,
            city=city,
            state=state,
            password=password
        )

        dealers = Dealer.objects.all()
        return render(request, 'portal/admin_dashboard.html', {
            'dealers': dealers,
            'message': f"Dealer {name} added successfully!"
        })

    dealers = Dealer.objects.all()
    return render(request, 'portal/admin_dashboard.html', {'dealers': dealers})

def dealer_login(request):
    if request.method == "POST":
        dealer_id = request.POST['dealer_id']
        password = request.POST['password']

        try:
            dealer = Dealer.objects.get(dealer_id=dealer_id, password=password)
            request.session['dealer_id'] = dealer.dealer_id
            return redirect('dealer_dashboard')
        except Dealer.DoesNotExist:
            return render(request, 'portal/dealer_login.html', {'error': 'Invalid Dealer ID or Password'})

    return render(request, 'portal/dealer_login.html')

def dealer_dashboard(request):
    dealer_id = request.session.get('dealer_id')
    if not dealer_id:
        return redirect('dealer_login')

    dealer = Dealer.objects.get(dealer_id=dealer_id)
    services_list = LabourService.objects.all()
    components_list = Component.objects.all()

    if request.method == "POST":
        cname = request.POST['customer_name']
        cphone = request.POST['customer_phone']
        sale_date = request.POST['date_of_sale']
        last_service = request.POST['last_service_date']
        kms = request.POST['service_kms']

        selected_services = request.POST.getlist('services')
        selected_components = request.POST.getlist('components')

        labour_total = 0
        component_total = 0

        # Create new service record
        record = ServiceRecord.objects.create(
            dealer=dealer,
            customer_name=cname,
            customer_phone=cphone,
            date_of_sale=sale_date,
            last_service_date=last_service,
            service_kms=kms
        )

        # Add selected services
        for sid in selected_services:
            service = LabourService.objects.get(id=sid)
            record.services.add(service)
            labour_total += service.cost

        # Add selected components and reduce inventory
        for cid in selected_components:
            component = Component.objects.get(id=cid)
            record.components.add(component)
            component_total += component.price

            # Reduce stock in inventory safely
            try:
                inventory = Inventory.objects.get(component=component)
                inventory.reduce_stock(1)
            except Inventory.DoesNotExist:
                print(f"No inventory record found for {component.part_name}")
            except ValueError as e:
                print(e)

        # Save total cost
        record.total_cost = labour_total + component_total
        record.save()

        return redirect('bill_view', record_id=record.id)

    # Show dashboard
    history = ServiceRecord.objects.filter(dealer=dealer).order_by('-created_at')
    
    dealer_inventory = Inventory.objects.filter(dealer=dealer)

    return render(request, 'portal/dealer_dashboard.html', {
        'dealer': dealer,
        'services': history,
        'labour_services': services_list,
        'components': components_list,
        'inventory': dealer_inventory
    })

def dealer_add_inventory(request):
    dealer_id = request.session.get('dealer_id')
    if not dealer_id:
        return redirect('dealer_login')

    dealer = Dealer.objects.get(dealer_id=dealer_id)
    components_list = Component.objects.all()

    if request.method == "POST":
        component_id = request.POST['component']
        quantity = int(request.POST['quantity'])

        component = Component.objects.get(id=component_id)
        inventory, created = Inventory.objects.get_or_create(
            dealer=dealer, component=component,
            defaults={'quantity': quantity, 'last_received_date': timezone.now()}
        )

        if not created:
            inventory.quantity += quantity
            inventory.last_received_date = timezone.now()
            inventory.save()

        messages.success(request, f"{quantity} pcs of '{component.part_name}' added successfully!")

        return redirect('dealer_add_inventory')

    dealer_inventory = Inventory.objects.filter(dealer=dealer).select_related('component')

    return render(request, 'portal/dealer_add_inventory.html', {
        'dealer': dealer,
        'components': components_list,
        'inventory': dealer_inventory
    })

    
from django.contrib import messages
from django.contrib.auth.decorators import login_required

# Simple login check: only admin-level users
def admin_manage_rates(request):
    # Later, you can add role check if you want
    services = LabourService.objects.all().order_by('job_code')

    if request.method == "POST":
        for s in services:
            new_cost = request.POST.get(f'cost_{s.id}')
            if new_cost and new_cost.isdigit():
                s.cost = int(new_cost)
                s.save()
        messages.success(request, "Rates updated successfully!")
        return redirect('admin_manage_rates')

    return render(request, 'portal/admin_manage_rates.html', {'services': services})

    
def bill_view(request, record_id):
    record = ServiceRecord.objects.get(id=record_id)
    services = record.services.all()
    return render(request, 'portal/bill.html', {
        'record': record,
        'services': services
    })

from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa

def download_bill_pdf(request, record_id):
    record = ServiceRecord.objects.get(id=record_id)
    services = record.services.all()
    template = get_template('portal/bill.html')
    html = template.render({'record': record, 'services': services})
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Bill_{record.id}.pdf"'
    pisa.CreatePDF(html, dest=response)
    return response
