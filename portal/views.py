from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.utils.crypto import get_random_string
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Dealer, ServiceRecord, LabourService, Component, Inventory, VehicleModel
from .models import Component
from django.utils import timezone
from openpyxl import Workbook
from django.utils.timezone import now
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
import json
import gspread, json
from oauth2client.service_account import ServiceAccountCredentials
from .utils import render_to_pdf
from django.template.loader import get_template
from xhtml2pdf import pisa
from .models import WarrantyClaim
import os
from .models import TestRide, CustomerFeedback, Dealer, Quotation, PDIInspection, Technician, DealerToDealerPurchase, DealerToDealerSale, FailedTagPart, WarrantyClaim, WarrantyPartPickup
from decimal import Decimal, InvalidOperation
from django.db import IntegrityError, transaction
import random, string, requests
from django.http import HttpResponse

def generate_service_id():
    prefix = "SMG-SRV-"
    random_part = get_random_string(length=4, allowed_chars='0123456789')
    return f"{prefix}{random_part}"

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

    service_id = request.POST.get("service_id")
    if not service_id:
        service_id = generate_service_id()

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
            service_id=service_id,
            customer_name=cname,
            customer_phone=cphone,
            date_of_sale=sale_date,
            last_service_date=last_service,
            service_kms=kms,
            battery_number=request.POST.get('battery_number'),
            jc_number=request.POST.get('jc_number'),
            motor_number=request.POST.get('motor_number')
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
        messages.success(request, "Service record saved successfully!")

        return redirect('bill_view', record_id=record.id)

    # GET render
    history = ServiceRecord.objects.filter(dealer=dealer).order_by('-created_at')
    dealer_inventory = Inventory.objects.filter(dealer=dealer)
    default_service_id = generate_service_id()

    return render(request, 'portal/dealer_dashboard.html', {
        'dealer': dealer,
        'services': history,
        'labour_services': services_list,
        'components': components_list,
        'inventory': dealer_inventory,
        'default_service_id': default_service_id
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
            'salesperson': request.POST.get('salesperson'),
        }

        # ✅ Save locally to DB
        TestRide.objects.create(**data)

        # ✅ Push to Google Sheet (Apps Script endpoint)
        GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbxIz5DSv1SQS0CNzzcvZo8nPyoDLpv6cgdjpjnDlv-BLo4MVtHdHCe01kmPg5A7xy8g/exec"

        # ✅ Attach dealer identity
        dealer_id = request.session.get('dealer_id')
        dealer_name = ""
        dealer_city = ""
        if dealer_id:
            try:
                d = Dealer.objects.get(dealer_id=dealer_id)
                dealer_name = getattr(d, "name", "") or getattr(d, "dealer_name", "")
                dealer_city = getattr(d, "city", "")
            except Dealer.DoesNotExist:
                pass

        payload = {**data, "dealer_id": dealer_id or "", "dealer_name": dealer_name, "dealer_city": dealer_city}

        try:
            response = requests.post(GOOGLE_SCRIPT_URL, json=payload)
            if response.status_code == 200:
                messages.success(request, "Test ride data saved and synced to Google Sheet successfully!")
            else:
                messages.warning(request, "Saved locally but failed to sync with Google Sheet.")
        except Exception as e:
            messages.warning(request, f"Saved locally. Sheet sync error: {e}")

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
                # ✅ Push to Google Sheet (Apps Script endpoint)
        GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbxF_HpPGAdXYK0-sdJ5mFogeLTCeNG5Kt68sRnFqtKvFyWvswYE3iMaaYliqLd0Y1c/exec"

        # ✅ Attach dealer identity
        dealer_id = request.session.get('dealer_id')
        dealer_name = ""
        dealer_city = ""
        if dealer_id:
            try:
                d = Dealer.objects.get(dealer_id=dealer_id)
                dealer_name = getattr(d, "name", "") or getattr(d, "dealer_name", "")
                dealer_city = getattr(d, "city", "")
            except Dealer.DoesNotExist:
                pass

        payload = {**data, "dealer_id": dealer_id or "", "dealer_name": dealer_name, "dealer_city": dealer_city}

        try:
            response = requests.post(GOOGLE_SCRIPT_URL, json=payload)
            if response.status_code == 200:
                messages.success(request, "Feedback submitted successfully and synced to Google Sheets!")
            else:
                messages.warning(request, "Feedback saved locally but Google Sheet sync failed.")
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

        # ✅ calculate total and save
        quotation.total_amount = (
            quotation.ex_showroom + quotation.rc + quotation.insurance +
            quotation.accessories + quotation.hypothecation + quotation.cow_cess
        )
        quotation.save()

        # ✅ Google Sheet Sync with Dealer Identity
        GOOGLE_QUOTATION_SHEET = "https://script.google.com/macros/s/AKfycbyjrhV1ExbfapB49v1rvG-vYX1WignWAUrk93dp2jBa8iCUmJdRzHwZtRpHjl1jmczO/exec"

        dealer_id = request.session.get('dealer_id')
        dealer_name = ""
        dealer_city = ""

        if dealer_id:
            try:
                d = Dealer.objects.get(dealer_id=dealer_id)
                dealer_name = getattr(d, "name", "") or getattr(d, "dealer_name", "")
                dealer_city = getattr(d, "city", "")
            except Dealer.DoesNotExist:
                pass

        payload = {
            "dealer_id": dealer_id or "",
            "dealer_name": dealer_name,
            "dealer_city": dealer_city,
            "customer_name": quotation.customer_name,
            "mobile_no": quotation.mobile_no,
            "city": quotation.city,
            "date": str(quotation.date_of_quotation),
            "ex_showroom": float(quotation.ex_showroom),
            "rc": float(quotation.rc),
            "insurance": float(quotation.insurance),
            "accessories": float(quotation.accessories),
            "hypothecation": float(quotation.hypothecation),
            "cow_cess": float(quotation.cow_cess),
            "total_amount": float(quotation.total_amount),
        }

        try:
            requests.post(GOOGLE_QUOTATION_SHEET, json=payload, timeout=10)
        except Exception as e:
            print("⚠️ Quotation Sheet Sync Error:", e)

        return redirect('quotation_pdf', quotation_id=quotation.id)

    quotations = Quotation.objects.filter(dealer=dealer).order_by('-created_at')
    return render(request, 'portal/dealer_quotation.html', {'dealer': dealer, 'quotations': quotations})

from django.template.loader import get_template
from xhtml2pdf import pisa

def quotation_pdf(request, quotation_id):
    quotation = get_object_or_404(Quotation, id=quotation_id)

    items = [
        {"part": "Ex Showroom", "qty": 1, "price": quotation.ex_showroom, "amount": quotation.ex_showroom},
        {"part": "RC", "qty": 1, "price": quotation.rc, "amount": quotation.rc},
        {"part": "Insurance", "qty": 1, "price": quotation.insurance, "amount": quotation.insurance},
        {"part": "Accessories", "qty": 1, "price": quotation.accessories, "amount": quotation.accessories},
        {"part": "Hypothecation", "qty": 1, "price": quotation.hypothecation, "amount": quotation.hypothecation},
        {"part": "Cow Cess", "qty": 1, "price": quotation.cow_cess, "amount": quotation.cow_cess},
    ]

    context = {
        "items": items,
        "total": quotation.total_amount,
    }

    template = get_template("portal/pdf/quotation_pdf.html")
    html = template.render(context)
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="Quotation_{quotation.customer_name}.pdf"'
    pisa.CreatePDF(html, dest=response)
    return response



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


def pdi_inspection_form(request):
    checklist_items = [
        "Lockset ON/OFF function",
        "Seat lock and Side lock function",
        "Instrument Cluster Functions / Battery Level Indication",
        "Electrical Part Check (Head light, Tail light, Horn, Indicators, USB Port)",
        "Throttle Operation Check",
        "Switch Function",
        "Brake Sensing Function",
        "Motor cut off while applying brake",
        "Tail light function / Brake sensing symbol",
        "Handle bar position / fitment",
        "Charging socket Proper Functioning",
        "Luggage box accessories confirmation",
        "Mirror",
        "Charger",
        "Tool kit",
        "Vin plate",
        "Chakori connector fitment",
        "MCB terminal wire connection fitment",
        "Front Wheel tyre (Seating/Wobbling/Air leakage)",
        "Rear Wheel tyre (Seating/Wobbling/Air leakage)",
        "PP parts aesthetic inspection",
        "Battery Clamp fitment",
        "Rear shocker function / Abnormal noise on test drive",
        "Battery charging upto 100%",
        "Test drive vehicle (min 5 km during PDI)",
        "Any other remark not mentioned above"
    ]

    if request.method == "POST":
        # Build results dict with safe defaults
        results = {}
        missing = []
        for idx, _ in enumerate(checklist_items, start=1):
            key = f"result_{idx}"
            val = request.POST.get(key)
            if val not in ("OK", "NG"):
                missing.append(idx)
            results[key] = val or "NG"

        if missing:
            messages.error(
                request,
                f"Please select OK/NG for all items. Missing rows: {', '.join(map(str, missing))}"
            )
            return render(request, "portal/pdi_inspection_form.html",
                          {"checklist": enumerate(checklist_items, start=1)})

        # Identify current dealer (from session)
        dealer_fk = None
        dealer_id = request.session.get('dealer_id')
        dealer_name = ""
        dealer_city = ""
        if dealer_id:
            try:
                dealer_fk = Dealer.objects.get(dealer_id=dealer_id)
                dealer_name = getattr(dealer_fk, "name", "") or getattr(dealer_fk, "dealer_name", "")
                dealer_city = getattr(dealer_fk, "city", "")
            except Dealer.DoesNotExist:
                pass

        # Save in DB
        PDIInspection.objects.create(
            dealer=dealer_fk,   # ✅ NOW VALID because model has dealer FK
            dealer_name=request.POST.get('dealer_name') or dealer_name,
            location=request.POST.get('location', ''),
            dealer_code=request.POST.get('dealer_code'),
            model_name=request.POST.get('model_name'),
            date=request.POST.get('date'),
            vin=request.POST.get('vin'),
            battery_no=request.POST.get('battery_no'),
            charger_no=request.POST.get('charger_no'),
            motor_no=request.POST.get('motor_no'),
            controller_no=request.POST.get('controller_no', ''),
            results=json.dumps(results),
            remarks=request.POST.get('remarks'),
        )

        # Push to Google Sheet (with dealer identity for filtering)
        try:
            GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbxxVxtarpCF__wFfgoiE57wuVjZyetksdcCvADmnENjjokWAGZQ1ZWYkQmD9EQ1DKr1jQ/exec"
            payload = {
                "dealer_id": dealer_id or "",
                "dealer_name": request.POST.get('dealer_name') or dealer_name,
                "dealer_city": dealer_city,
                "dealer_code": request.POST.get('dealer_code'),
                "model_name": request.POST.get('model_name'),
                "date": request.POST.get('date'),
                "vin": request.POST.get('vin'),
                "battery_no": request.POST.get('battery_no'),
                "charger_no": request.POST.get('charger_no'),
                "motor_no": request.POST.get('motor_no'),
                "controller_no": request.POST.get('controller_no', ''),
                "results": results,
                "remarks": request.POST.get('remarks', ''),
            }
            r = requests.post(GOOGLE_SCRIPT_URL, json=payload, timeout=12)
            if r.status_code != 200:
                messages.warning(request, "PDI saved. Google Sheet sync failed.")
        except Exception as e:
            messages.warning(request, f"PDI saved. Sheet sync error: {e}")

        messages.success(request, "PDI inspection submitted successfully!")
        return redirect('pdi_inspection_form')

    # GET
    return render(
        request,
        "portal/pdi_inspection_form.html",
        {"checklist": enumerate(checklist_items, start=1)}
    )


def pdi_list(request):
    import json
    dealer_id = request.session.get('dealer_id')
    if not dealer_id:
        return redirect('dealer_login')

    try:
        dealer = Dealer.objects.get(dealer_id=dealer_id)
    except Dealer.DoesNotExist:
        messages.error(request, "Dealer not found.")
        return redirect('dealer_login')

    # ✅ Only show records properly linked to this dealer
    rows = PDIInspection.objects.filter(dealer=dealer).order_by('-id')

    pdi_data = []
    for r in rows:
        try:
            data = json.loads(r.results or "{}")
            row_status = "NG" if any(v == "NG" for v in data.values()) else "OK"
        except Exception:
            row_status = "OK"

        pdi_data.append({
            "date": r.date,
            "model_name": r.model_name,
            "vin": r.vin,
            "status": row_status,
        })

    return render(request, "portal/pdi_list.html", {"pdi_data": pdi_data})



def my_service_records(request):
    dealer_id = request.session.get('dealer_id')
    if not dealer_id:
        return redirect('dealer_login')

    dealer = Dealer.objects.get(dealer_id=dealer_id)

    records = ServiceRecord.objects.filter(dealer=dealer).order_by('-created_at')

    return render(request, "portal/my_service_records.html", {"records": records})

def technician_list(request):
    if request.method == "POST":
        name = request.POST.get("name")
        mobile_number = request.POST.get("mobile_number")
        date_of_joining = request.POST.get("date_of_joining")
        address = request.POST.get("address")
        trainings_done = request.POST.get("trainings_done")
        training_certification = request.POST.get("training_certification") == "on"

        Technician.objects.create(
            name=name,
            mobile_number=mobile_number,
            date_of_joining=date_of_joining,
            address=address,
            trainings_done=trainings_done,
            training_certification=training_certification
        )
        messages.success(request, "Technician added successfully!")
        return redirect('technician_list')

    technicians = Technician.objects.all().order_by('-created_at')
    return render(request, "portal/technician_list.html", {'technicians': technicians})


def delete_technician(request, id):
    tech = get_object_or_404(Technician, id=id)
    tech.delete()
    messages.success(request, "Technician deleted successfully!")
    return redirect('technician_list')

def edit_technician(request, id):
    tech = get_object_or_404(Technician, id=id)
    if request.method == "POST":
        tech.name = request.POST.get("name")
        tech.mobile_number = request.POST.get("mobile_number")
        tech.date_of_joining = request.POST.get("date_of_joining")
        tech.address = request.POST.get("address")
        tech.trainings_done = request.POST.get("trainings_done")
        tech.training_certification = request.POST.get("training_certification") == "on"
        tech.save()
        messages.success(request, "Technician updated successfully!")
        return redirect('technician_list')
    return render(request, "portal/edit_technician.html", {"tech": tech})


# --- DEALER TO DEALER SALE ---
def dealer_sale_list(request):
    sales = DealerToDealerSale.objects.all().order_by('-created_at')
    return render(request, "portal/dealer_sale_list.html", {"sales": sales})

def dealer_sale_add(request):
    if request.method == "POST":
        data = {
            "primary_dealer_name": request.POST.get("primary_dealer_name"),
            "primary_gst": request.POST.get("primary_gst"),
            "primary_code": request.POST.get("primary_code"),
            "primary_phone": request.POST.get("primary_phone"),
            "primary_email": request.POST.get("primary_email"),
            "primary_address": request.POST.get("primary_address"),

            "secondary_dealer_name": request.POST.get("secondary_dealer_name"),
            "secondary_gst": request.POST.get("secondary_gst"),
            "secondary_code": request.POST.get("secondary_code"),
            "secondary_phone": request.POST.get("secondary_phone"),
            "secondary_email": request.POST.get("secondary_email"),
            "secondary_address": request.POST.get("secondary_address"),

            "date_of_sale": request.POST.get("date_of_sale"),
            "model_name": request.POST.get("model_name"),
            "product_color": request.POST.get("product_color"),
            "battery_number": request.POST.get("battery_number"),
            "chasis_number": request.POST.get("chasis_number"),
            "motor_number": request.POST.get("motor_number"),
            "product_code": request.POST.get("product_code"),
            "price": request.POST.get("price"),

            "sales_rep_name": request.POST.get("sales_rep_name"),
            "sales_rep_mobile": request.POST.get("sales_rep_mobile"),
            "sales_rep_email": request.POST.get("sales_rep_email"),
        }

        # ✅ Save locally
        DealerToDealerSale.objects.create(**data)

        # ✅ Google Sheet Integration with Dealer Identity
        GOOGLE_SHEET_SALE = "https://script.google.com/macros/s/AKfycbyKkJTIGyorpE5XWKa17elvHDiXDCslN3tiOftL-Ds6y1ZIjXpqxrQqB7Lgcuece5O7pg/exec"

        dealer_id = request.session.get('dealer_id')
        dealer_name = ""
        dealer_city = ""

        if dealer_id:
            try:
                d = Dealer.objects.get(dealer_id=dealer_id)
                dealer_name = getattr(d, "name", "") or getattr(d, "dealer_name", "")
                dealer_city = getattr(d, "city", "")
            except Dealer.DoesNotExist:
                pass

        payload = {**data, "dealer_id": dealer_id or "", "dealer_name": dealer_name, "dealer_city": dealer_city}

        try:
            response = requests.post(GOOGLE_SHEET_SALE, json=payload)
            if response.status_code == 200:
                messages.success(request, "✅ Dealer Sale saved and synced to Google Sheet!")
            else:
                messages.warning(request, "✅ Saved locally but Google Sheet sync failed.")
        except Exception as e:
            messages.warning(request, f"✅ Saved locally. Sheet sync error: {e}")

        return redirect('dealer_sale_list')

    return render(request, "portal/dealer_sale_add.html")


def delete_dealer_sale(request, id):
    sale = get_object_or_404(DealerToDealerSale, id=id)
    sale.delete()
    messages.success(request, "🗑️ Sale record deleted successfully!")
    return redirect('dealer_sale_list')


# --- DEALER TO DEALER PURCHASE ---
def dealer_purchase_list(request):
    purchases = DealerToDealerPurchase.objects.all().order_by('-created_at')
    return render(request, "portal/dealer_purchase_list.html", {"purchases": purchases})


def dealer_purchase_add(request):
    if request.method == "POST":
        data = {
            "primary_dealer_name": request.POST.get("primary_dealer_name"),
            "primary_gst": request.POST.get("primary_gst"),
            "primary_code": request.POST.get("primary_code"),
            "primary_phone": request.POST.get("primary_phone"),
            "primary_email": request.POST.get("primary_email"),
            "primary_address": request.POST.get("primary_address"),

            "secondary_dealer_name": request.POST.get("secondary_dealer_name"),
            "secondary_gst": request.POST.get("secondary_gst"),
            "secondary_code": request.POST.get("secondary_code"),
            "secondary_phone": request.POST.get("secondary_phone"),
            "secondary_email": request.POST.get("secondary_email"),
            "secondary_address": request.POST.get("secondary_address"),

            "date_of_purchase": request.POST.get("date_of_purchase"),
            "model_name": request.POST.get("model_name"),
            "product_color": request.POST.get("product_color"),
            "battery_number": request.POST.get("battery_number"),
            "chasis_number": request.POST.get("chasis_number"),
            "motor_number": request.POST.get("motor_number"),
            "product_code": request.POST.get("product_code"),
            "price": request.POST.get("price"),

            "purchase_rep_name": request.POST.get("purchase_rep_name"),
            "purchase_rep_mobile": request.POST.get("purchase_rep_mobile"),
            "purchase_rep_email": request.POST.get("purchase_rep_email"),
        }

        # ✅ Save locally
        DealerToDealerPurchase.objects.create(**data)

        # ✅ Google Sheet Integration with Dealer Identity
        GOOGLE_SHEET_PURCHASE = "https://script.google.com/macros/s/AKfycbw4TQ2G4QCyvuo5lF66GYxU7VCcV_qTwQ0ofAjy87IoxDfJzmdbqwoiWRkv2cnX3_wh/exec"

        dealer_id = request.session.get('dealer_id')
        dealer_name = ""
        dealer_city = ""

        if dealer_id:
            try:
                d = Dealer.objects.get(dealer_id=dealer_id)
                dealer_name = getattr(d, "name", "") or getattr(d, "dealer_name", "")
                dealer_city = getattr(d, "city", "")
            except Dealer.DoesNotExist:
                pass

        payload = {**data, "dealer_id": dealer_id or "", "dealer_name": dealer_name, "dealer_city": dealer_city}

        try:
            response = requests.post(GOOGLE_SHEET_PURCHASE, json=payload)
            if response.status_code == 200:
                messages.success(request, "✅ Dealer Purchase saved and synced to Google Sheet!")
            else:
                messages.warning(request, "✅ Saved locally but Google Sheet sync failed.")
        except Exception as e:
            messages.warning(request, f"✅ Saved locally. Sheet sync error: {e}")

        return redirect('dealer_purchase_list')

    return render(request, "portal/dealer_purchase_add.html")


def delete_dealer_purchase(request, id):
    purchase = get_object_or_404(DealerToDealerPurchase, id=id)
    purchase.delete()
    messages.success(request, "🗑️ Purchase record deleted successfully!")
    return redirect('dealer_purchase_list')


# ==============================
# ✅ Excel Export Functions
# ==============================
from openpyxl import Workbook
from django.http import HttpResponse

def export_sales_excel(request):
    sales = DealerToDealerSale.objects.all().order_by('-id')
    wb = Workbook()
    ws = wb.active
    ws.title = "Dealer Sales"

    headers = [
        "Primary Dealer", "Secondary Dealer", "Model", "Date of Sale", "Battery No",
        "Motor No", "Product Code", "Price", "Sales Rep"
    ]
    ws.append(headers)

    for s in sales:
        ws.append([
            s.primary_dealer_name, s.secondary_dealer_name, s.model_name,
            s.date_of_sale, s.battery_number, s.motor_number,
            s.product_code, s.price, s.sales_rep_name
        ])

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = "attachment; filename=Dealer_Sales.xlsx"
    wb.save(response)
    return response


def export_purchases_excel(request):
    purchases = DealerToDealerPurchase.objects.all().order_by('-id')
    wb = Workbook()
    ws = wb.active
    ws.title = "Dealer Purchases"

    headers = [
        "Primary Dealer", "Secondary Dealer", "Model", "Date of Purchase", "Battery No",
        "Motor No", "Product Code", "Price", "Purchase Rep"
    ]
    ws.append(headers)

    for p in purchases:
        ws.append([
            p.primary_dealer_name, p.secondary_dealer_name, p.model_name,
            p.date_of_purchase, p.battery_number, p.motor_number,
            p.product_code, p.price, p.purchase_rep_name
        ])

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = "attachment; filename=Dealer_Purchases.xlsx"
    wb.save(response)
    return response

def warranty_home(request):
    return render(request, "portal/warranty_home.html")

def failed_tag_form(request):
    dealer_fk = None
    dealer_id = request.session.get("dealer_id")
    dealer_name = ""

    if dealer_id:
        try:
            dealer_fk = Dealer.objects.get(dealer_id=dealer_id)
            dealer_name = dealer_fk.name
        except Dealer.DoesNotExist:
            pass
        
    if request.method == "POST":
        FailedTagPart.objects.create(
            dealer=dealer_fk,
            dealer_id_val=dealer_id,
            dealer_name_val=dealer_name,
            dealer_name=request.POST.get("dealer_name"),
            service_order_no=request.POST.get("service_order_no"),
            warranty_type=request.POST.get("warranty_type"),
            model_no=request.POST.get("model_no"),
            odo_reading=request.POST.get("odo_reading"),
            chassis_no=request.POST.get("chassis_no"),
            customer_sale_date=request.POST.get("customer_sale_date"),
            part_description=request.POST.get("part_description"),
            part_serial_number=request.POST.get("part_serial_number"),
            customer_complaint=request.POST.get("customer_complaint"),
            diagnostic_details=request.POST.get("diagnostic_details"),
            remarks=request.POST.get("remarks")
        )
        # GOOGLE SHEET SYNC
        import requests

        GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzmOuIfybIkcQM8UBfy2wNetXe15Ecdnvh9eJIJ9wVW4jxYRJs4Nrm_v3ib0EZTlEdsCg/exec"

        payload = {
            "dealer_id": dealer_id,
            "dealer_name": dealer_name,
            "form_type": "failed_tag",
            "data": {
                "service_order_no": request.POST.get("service_order_no"),
                "warranty_type": request.POST.get("warranty_type"),
                "model_no": request.POST.get("model_no"),
                "chassis_no": request.POST.get("chassis_no"),
                "part_description": request.POST.get("part_description"),
                "part_serial_number": request.POST.get("part_serial_number"),
            }
        }

        try:
            requests.post(GOOGLE_SCRIPT_URL, json=payload, timeout=10)
        except:
            pass

        messages.success(request, "Failed Tag Part form saved successfully!")
        return redirect('failed_tag_form')
    return render(request, "portal/failed_tag_form.html")

def failed_tag_list(request):
    dealer_id = request.session.get('dealer_id')
    if not dealer_id:
        return redirect('dealer_login')
    
    dealer = Dealer.objects.get(dealer_id=dealer_id)

    rows = FailedTagPart.objects.filter(dealer=dealer).order_by('-id')

    return render(request, 'portal/failed_tag_list.html', {"rows": rows})

def warranty_claim_form(request):
    dealer_fk = None
    dealer_id = request.session.get("dealer_id")
    dealer_name = ""

    if dealer_id:
        try:
            dealer_fk = Dealer.objects.get(dealer_id=dealer_id)
            dealer_name = getattr(dealer_fk, "name", "")
        except Dealer.DoesNotExist:
            pass
        
    if request.method == "POST":
        data = {
            "dealer": dealer_fk,
            "dealer_id_val": dealer_id,
            "dealer_name_val": dealer_name,
            "component": request.POST.get("component"),
            "material_code": request.POST.get("material_code"),
            "reason_for_replacement": request.POST.get("reason_for_replacement"),
            "last_service_details": json.dumps({
                "service1": request.POST.get("service1"),
                "service2": request.POST.get("service2"),
                "service3": request.POST.get("service3"),
                "service4": request.POST.get("service4"),
                "service5": request.POST.get("service5"),
            }),
            "technical_details": request.POST.get("technical_details"),
            "customer_signature": request.POST.get("customer_signature"),
            "dealer_signature": request.POST.get("dealer_signature"),
        }
        WarrantyClaim.objects.create(**data)
        import requests

        GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzmOuIfybIkcQM8UBfy2wNetXe15Ecdnvh9eJIJ9wVW4jxYRJs4Nrm_v3ib0EZTlEdsCg/exec"

        payload = {
            "dealer_id": dealer_id,
            "dealer_name": dealer_name,
            "form_type": "warranty_claim",
            "data": {
                "component": request.POST.get("component"),
                "material_code": request.POST.get("material_code"),
                "reason_for_replacement": request.POST.get("reason_for_replacement"),
                "technical_details": request.POST.get("technical_details"),
            }
        }

        try:
            requests.post(GOOGLE_SCRIPT_URL, json=payload, timeout=10)
        except:
            pass

        messages.success(request, "Warranty Claim form saved successfully!")
        return redirect('warranty_claim_form')

    return render(request, "portal/warranty_claim_form.html")

def warranty_claim_list(request):
    dealer_id = request.session.get('dealer_id')
    if not dealer_id:
        return redirect('dealer_login')
    
    dealer = Dealer.objects.get(dealer_id=dealer_id)

    rows = WarrantyClaim.objects.filter(dealer=dealer).order_by('-id')

    return render(request, 'portal/warranty_claim_list.html', {"rows": rows})


def warranty_pickup_form(request):
    dealer_fk = None
    dealer_id = request.session.get("dealer_id")
    dealer_name = ""

    if dealer_id:
        try:
            dealer_fk = Dealer.objects.get(dealer_id=dealer_id)
            dealer_name = getattr(dealer_fk, "name", "")
        except Dealer.DoesNotExist:
            pass

    if request.method == "POST":
        materials = []
        for i in range(1, 11):
            row = {
                "so_number": request.POST.get(f"so_{i}"),
                "chassis_no": request.POST.get(f"chassis_{i}"),
                "model": request.POST.get(f"model_{i}"),
                "component_name": request.POST.get(f"component_{i}"),
                "serial_no": request.POST.get(f"serial_{i}"),
                "vendor": request.POST.get(f"vendor_{i}"),
                "amount": request.POST.get(f"amount_{i}")
            }
            if any(row.values()):
                materials.append(row)

        WarrantyPartPickup.objects.create(
            dealer=dealer_fk,
            dealer_id_val=dealer_id,
            dealer_name_val=dealer_name,
            collection_address=request.POST.get("collection_address"),
            delivery_address=request.POST.get("delivery_address"),
            contact_person=request.POST.get("contact_person"),
            mobile_no=request.POST.get("mobile_no"),
            boxes=request.POST.get("boxes"),
            total_weight=request.POST.get("total_weight"),
            approx_weight=request.POST.get("approx_weight"),
            material_details=json.dumps(materials)
        )
        import requests

        GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzmOuIfybIkcQM8UBfy2wNetXe15Ecdnvh9eJIJ9wVW4jxYRJs4Nrm_v3ib0EZTlEdsCg/exec"

        payload = {
            "dealer_id": dealer_id,
            "dealer_name": dealer_name,
            "form_type": "warranty_pickup",
            "data": {
                "collection_address": request.POST.get("collection_address"),
                "delivery_address": request.POST.get("delivery_address"),
                "contact_person": request.POST.get("contact_person"),
                "mobile_no": request.POST.get("mobile_no"),
            }
        }

        try:
            requests.post(GOOGLE_SCRIPT_URL, json=payload, timeout=10)
        except:
            pass

        messages.success(request, "Warranty Part Pickup form saved successfully!")
        return redirect('warranty_pickup_form')

    return render(request, "portal/warranty_pickup_form.html")

def warranty_pickup_list(request):
    dealer_id = request.session.get('dealer_id')
    if not dealer_id:
        return redirect('dealer_login')
    
    dealer = Dealer.objects.get(dealer_id=dealer_id)

    rows = WarrantyPartPickup.objects.filter(dealer=dealer).order_by('-id')

    return render(request, 'portal/warranty_pickup_list.html', {"rows": rows})


def failed_tag_pdf(request, pk):
    item = FailedTagPart.objects.get(pk=pk)
    pdf = render_to_pdf('portal/pdf/failed_tag_pdf.html', {"item": item})
    return pdf

def warranty_claim_pdf(request, pk):
    claim = WarrantyClaim.objects.get(pk=pk)
    pdf = render_to_pdf('portal/pdf/warranty_claim_pdf.html', {'claim': claim})
    return pdf

def warranty_pickup_pdf(request, pk):
    pickup = WarrantyPartPickup.objects.get(pk=pk)
    materials = json.loads(pickup.material_details)
    pdf = render_to_pdf('portal/pdf/warranty_pickup_pdf.html', {'pickup': pickup, 'materials': materials})
    return pdf
