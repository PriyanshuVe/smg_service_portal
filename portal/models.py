from django.db import models

class Dealer(models.Model):
    dealer_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    contact = models.CharField(max_length=15)
    location = models.CharField(max_length=100)
    city = models.CharField(max_length=50)
    state = models.CharField(max_length=50)
    password = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.name} ({self.dealer_id})"
    
class LabourService(models.Model):
    job_code = models.CharField(max_length=10)
    description = models.CharField(max_length=200)
    cost = models.IntegerField()

    def __str__(self):
        return f"{self.description} - ₹{self.cost}"
    
class VehicleModel(models.Model):
    """Represents vehicle models like Model 1, Model 2 etc."""
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class Component(models.Model):
    part_code = models.CharField(max_length=10, unique=True)
    part_name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.part_name} ({self.part_code})"


# ✅ New model for inventory tracking    
class Inventory(models.Model):
    dealer = models.ForeignKey('Dealer', on_delete=models.CASCADE)  # linked to each dealer
    component = models.ForeignKey('Component', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=0)
    last_received_date = models.DateField(auto_now=True)

    def __str__(self):
        return f"{self.dealer.name} - {self.component.part_name}: {self.quantity} pcs"

    def reduce_stock(self, used_count=1):
        """Reduce stock when component is replaced."""
        if self.quantity < used_count:
            raise ValueError(f"Not enough stock for {self.component.part_name}!")
        self.quantity -= used_count
        self.save()


class ServiceRecord(models.Model):
    dealer = models.ForeignKey(Dealer, on_delete=models.CASCADE)
    customer_name = models.CharField(max_length=100)
    customer_phone = models.CharField(max_length=15)
    date_of_sale = models.DateField()
    last_service_date = models.DateField()
    service_kms = models.IntegerField()
    services = models.ManyToManyField(LabourService, blank=True)
    components = models.ManyToManyField('Component', blank=True)  # newly added
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer_name} ({self.dealer.name})"


class TestRide(models.Model):
    name = models.CharField(max_length=100)
    mobile = models.CharField(max_length=15)
    occupation = models.CharField(max_length=50, blank=True, null=True)
    age = models.IntegerField(blank=True, null=True)
    city = models.CharField(max_length=50)
    model_name = models.CharField(max_length=100)
    date_of_test_ride = models.DateField()
    expectations = models.CharField(max_length=200, blank=True, null=True)
    budget = models.CharField(max_length=50, blank=True, null=True)
    reference = models.CharField(max_length=100, blank=True, null=True)
    salesperson = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.model_name}"

    
class CustomerFeedback(models.Model):
    customer_name = models.CharField(max_length=100)
    dealership_name = models.CharField(max_length=100)
    contact_number = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    city_name = models.CharField(max_length=50)
    reason_for_visit = models.CharField(max_length=200, blank=True, null=True)
    date_of_visit = models.DateField()
    date_of_birth = models.DateField(blank=True, null=True)
    staff_behaviour = models.CharField(max_length=20)
    services_rating = models.CharField(max_length=20)
    purchase_experience = models.CharField(max_length=20)
    lounge_experience = models.CharField(max_length=20)
    access_lounge = models.CharField(max_length=5)
    schemes_explained = models.CharField(max_length=5)
    queries_resolved = models.CharField(max_length=5)
    benefits_discussed = models.CharField(max_length=5)
    overall_rating = models.IntegerField()
    remarks = models.TextField(blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer_name} - {self.dealership_name}"

class Quotation(models.Model):
    dealer = models.ForeignKey(Dealer, on_delete=models.CASCADE)
    customer_name = models.CharField(max_length=100)
    mobile_no = models.CharField(max_length=15)
    city = models.CharField(max_length=50)
    date_of_quotation = models.DateField()
    
    ex_showroom = models.DecimalField(max_digits=10, decimal_places=2)
    rc = models.DecimalField(max_digits=10, decimal_places=2)
    insurance = models.DecimalField(max_digits=10, decimal_places=2)
    accessories = models.DecimalField(max_digits=10, decimal_places=2)
    hypothecation = models.DecimalField(max_digits=10, decimal_places=2)
    cow_cess = models.DecimalField(max_digits=10, decimal_places=2)

    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.total_amount = (
            self.ex_showroom + self.rc + self.insurance +
            self.accessories + self.hypothecation + self.cow_cess
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Quotation for {self.customer_name} ({self.date_of_quotation})"

class PDIInspection(models.Model):
    dealer_name = models.CharField(max_length=100)
    location = models.CharField(max_length=100)
    dealer_code = models.CharField(max_length=50)
    model_name = models.CharField(max_length=50)
    date = models.DateField()
    vin = models.CharField(max_length=50)
    battery_no = models.CharField(max_length=50)
    charger_no = models.CharField(max_length=50)
    motor_no = models.CharField(max_length=50)
    controller_no = models.CharField(max_length=50)
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"PDI – {self.model_name} ({self.vin})"
