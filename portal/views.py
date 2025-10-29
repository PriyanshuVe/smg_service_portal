from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Dealer, ServiceRecord, LabourService, Component, Inventory, VehicleModel
from .models import Component
from django.utils import timezone
from openpyxl import Workbook
from django.utils.timezone import now
from django.contrib import messages
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from .models import TestRide, CustomerFeedback, Quotation
from decimal import Decimal, InvalidOperation
from django.db import IntegrityError, transaction
import random, string, requests
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

        try:
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
            messages.success(request, f"Dealer {name} added successfully!")
        except IntegrityError:
            messages.error(request, f"Email {email} already exists! Please use a different one.")

    # Always show dealer list
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

from decimal import Decimal, InvalidOperation

def dealer_dashboard(request):
    dealer_id = request.session.get('dealer_id')
    if not dealer_id:
        return redirect('dealer_login')

    dealer = Dealer.objects.get(dealer_id=dealer_id)
    services_list = LabourService.objects.all()
    components_list = Component.objects.all()

    if request.method == "POST":
        cname = request.POST.get('customer_name', '').strip()
        cphone = request.POST.get('customer_phone', '').strip()
        sale_date = request.POST.get('date_of_sale')
        last_service = request.POST.get('last_service_date')
        kms = request.POST.get('service_kms')

        selected_services = request.POST.getlist('services')       # matches name in template
        selected_components = request.POST.getlist('components')   # matches name in template

        labour_total = Decimal(0)
        component_total = Decimal(0)

        # create record
        record = ServiceRecord.objects.create(
            dealer=dealer,
            customer_name=cname,
            customer_phone=cphone,
            date_of_sale=sale_date,
            last_service_date=last_service,
            service_kms=kms
        )

        # add selected services
        for sid in selected_services:
            try:
                service = LabourService.objects.get(id=int(sid))
                record.services.add(service)
                labour_total += Decimal(service.cost)
            except (LabourService.DoesNotExist, ValueError):
                continue

        # add selected components and reduce dealer inventory safely
        for cid in selected_components:
            try:
                component = Component.objects.get(id=int(cid))
                record.components.add(component)
                # ensure Decimal from price (which may be Decimal already)
                component_total += Decimal(str(component.price))

                # reduce stock for this dealer only
                try:
                    inventory = Inventory.objects.get(dealer=dealer, component=component)
                    inventory.reduce_stock(1)
                except Inventory.DoesNotExist:
                    # no stock for this dealer — we don't crash, just log
                    print(f"[WARN] No inventory record for {component.part_name} (dealer {dealer.dealer_id})")
                except ValueError as e:
                    print(f"[WARN] Inventory reduce error: {e}")

            except (Component.DoesNotExist, ValueError):
                continue

        # save totals (DecimalField)
        record.total_cost = labour_total + component_total
        record.save()

        return redirect('bill_view', record_id=record.id)

    # GET render
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

def delete_inventory(request, item_id):
    dealer_id = request.session.get('dealer_id')
    if not dealer_id:
        return redirect('dealer_login')
    dealer = Dealer.objects.get(dealer_id=dealer_id)
    inventory_item = get_object_or_404(Inventory, id=item_id, dealer=dealer)
    inventory_item.delete()
    messages.success(request, "Stock item deleted successfully!")
    return redirect('dealer_add_inventory')

    
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
    record = get_object_or_404(ServiceRecord, id=record_id)
    services = record.services.all()
    components_qs = record.components.all()

    labour_total = sum(Decimal(s.cost) for s in services) if services else Decimal(0)
    component_total = sum(Decimal(str(c.price)) for c in components_qs) if components_qs else Decimal(0)
    grand_total = labour_total + component_total

    # Ensure record.total_cost is set correctly (safety)
    if record.total_cost != grand_total:
        record.total_cost = grand_total
        record.save()

    context = {
        "record": record,
        "services": services,
        "components": [
            {"code": c.part_code, "name": c.part_name, "price": c.price} for c in components_qs
        ],
        "labour_total": labour_total,
        "component_total": component_total,
        "grand_total": grand_total,
    }
    return render(request, 'portal/bill.html', context)


from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa

def download_bill_pdf(request, record_id):
    record = get_object_or_404(ServiceRecord, id=record_id)

    services = record.services.all()

    components_data = []
    for component in record.components.all():
        components_data.append({
            "name": component.part_name,
            "code": component.part_code,
            "price": component.price,
        })

    context = {
        "record": record,
        "services": services,
        "components": components_data,
        "total_cost": record.total_cost,
    }

    # ✅ Render bill as HTML → convert to PDF
    template = get_template('portal/bill.html')
    html = template.render(context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Bill_{record.id}.pdf"'
    pisa.CreatePDF(html, dest=response)
    return response


def edit_dealer(request, dealer_id):
    dealer = get_object_or_404(Dealer, id=dealer_id)   # numeric pk
    if request.method == "POST":
        dealer.name = request.POST.get("name")
        dealer.email = request.POST.get("email")
        dealer.contact = request.POST.get("contact")
        dealer.location = request.POST.get("location")
        dealer.city = request.POST.get("city")
        dealer.state = request.POST.get("state")
        dealer.save()
        messages.success(request, "Dealer updated successfully!")
        return redirect("admin_dashboard")
    return render(request, "portal/edit_dealer.html", {"dealer": dealer})


def delete_dealer(request, dealer_id):
    dealer = get_object_or_404(Dealer, id=dealer_id)   # numeric pk
    dealer.delete()
    messages.success(request, "Dealer deleted successfully!")
    return redirect("admin_dashboard")


def test_ride_form(request):
    if request.method == "POST":
        data = {
            'name': request.POST.get('name'),
            'mobile': request.POST.get('mobile'),
            'occupation': request.POST.get('occupation'),
            'age': request.POST.get('age'),
            'city': request.POST.get('city'),
            'model_name': request.POST.get('model_name'),
            'date_of_test_ride': request.POST.get('date_of_test_ride'),
            'expectations': request.POST.get('expectations'),
            'budget': request.POST.get('budget'),
            'reference': request.POST.get('reference'),
            'salesperson': request.POST.get('salesperson')
        }

        # ✅ Save to Database
        TestRide.objects.create(**data)

        # ✅ Try saving to Google Sheet only if credentials file exists
        try:
            if os.path.exists("google_creds.json"):
                scope = ["https://spreadsheets.google.com/feeds",
                         "https://www.googleapis.com/auth/drive"]
                creds = ServiceAccountCredentials.from_json_keyfile_name("google_creds.json", scope)
                client = gspread.authorize(creds)
                sheet = client.open("SMG Test Ride Data").sheet1
                sheet.append_row(list(data.values()))
                print("✅ Data also saved to Google Sheet.")
            else:
                print("⚠️ google_creds.json not found — skipping sheet save.")
        except Exception as e:
            print("❌ Google Sheet error:", e)

        messages.success(request, "Test ride data saved successfully!")
        return redirect('test_ride_form')

    return render(request, "portal/test_ride_form.html")

def customer_feedback_form(request):
    if request.method == "POST":
        data = {field: request.POST.get(field) for field in [
            'customer_name', 'dealership_name', 'contact_number', 'email',
            'city_name', 'reason_for_visit', 'date_of_visit', 'date_of_birth',
            'staff_behaviour', 'services_rating', 'purchase_experience', 'lounge_experience',
            'access_lounge', 'schemes_explained', 'queries_resolved', 'benefits_discussed',
            'overall_rating', 'remarks'
        ]}

        CustomerFeedback.objects.create(**data)
         # Push to Google Sheets
        try:
            response = requests.post("https://script.google.com/macros/s/AKfycbxF_HpPGAdXYK0-sdJ5mFogeLTCeNG5Kt68sRnFqtKvFyWvswYE3iMaaYliqLd0Y1c/exec", json=data)
            if response.status_code == 200:
                messages.success(request, "Feedback submitted successfully and synced to Google Sheets!")
            else:
                messages.warning(request, "Feedback saved locally but failed to sync with Google Sheet.")
        except Exception as e:
            messages.warning(request, f"Feedback saved locally. Sheet sync error: {e}")

        return redirect('customer_feedback_form')

    return render(request, "portal/customer_feedback_form.html")

def dealer_quotation(request):
    dealer_id = request.session.get('dealer_id')
    if not dealer_id:
        return redirect('dealer_login')
    dealer = Dealer.objects.get(dealer_id=dealer_id)

    if request.method == "POST":
        customer_name = request.POST.get("customer_name")
        mobile_no = request.POST.get("mobile_no")
        city = request.POST.get("city")
        date_of_quotation = request.POST.get("date_of_quotation")

        ex_showroom = Decimal(request.POST.get("ex_showroom", "0"))
        rc = Decimal(request.POST.get("rc", "0"))
        insurance = Decimal(request.POST.get("insurance", "0"))
        accessories = Decimal(request.POST.get("accessories", "0"))
        hypothecation = Decimal(request.POST.get("hypothecation", "0"))
        cow_cess = Decimal(request.POST.get("cow_cess", "0"))

        quotation = Quotation.objects.create(
            dealer=dealer,
            customer_name=customer_name,
            mobile_no=mobile_no,
            city=city,
            date_of_quotation=date_of_quotation,
            ex_showroom=ex_showroom,
            rc=rc,
            insurance=insurance,
            accessories=accessories,
            hypothecation=hypothecation,
            cow_cess=cow_cess,
        )

        return redirect('download_quotation_excel', quotation_id=quotation.id)

    quotations = Quotation.objects.filter(dealer=dealer).order_by('-created_at')
    return render(request, 'portal/dealer_quotation.html', {'dealer': dealer, 'quotations': quotations})


def download_quotation_excel(request, quotation_id):
    quotation = get_object_or_404(Quotation, id=quotation_id)
    wb = Workbook()
    ws = wb.active
    ws.title = "Quotation"

    ws.append(["SMG Electric - Quotation"])
    ws.append(["Customer Name", quotation.customer_name])
    ws.append(["Mobile No", quotation.mobile_no])
    ws.append(["City", quotation.city])
    ws.append(["Date", quotation.date_of_quotation.strftime("%d-%m-%Y")])
    ws.append([])

    ws.append(["Details", "Amount (₹)"])
    ws.append(["Ex Showroom", quotation.ex_showroom])
    ws.append(["RC", quotation.rc])
    ws.append(["Insurance", quotation.insurance])
    ws.append(["Accessories", quotation.accessories])
    ws.append(["Hypothecation", quotation.hypothecation])
    ws.append(["Cow Cess", quotation.cow_cess])
    ws.append([])
    ws.append(["Total", quotation.total_amount])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"Quotation_{quotation.customer_name}_{now().strftime('%Y%m%d')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename={filename}'
    wb.save(response)
    return response