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

    
    
    