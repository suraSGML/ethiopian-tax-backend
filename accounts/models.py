import uuid
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('role', User.Role.SUPER_ADMIN)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        TAXPAYER = 'taxpayer', 'Taxpayer'
        TAX_OFFICER = 'tax_officer', 'Tax Officer'
        SUPER_ADMIN = 'super_admin', 'Super Admin'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    tin = models.CharField(max_length=20, unique=True, null=True, blank=True, verbose_name='Tax Identification Number')
    phone = PhoneNumberField(null=True, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.TAXPAYER)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(null=True, blank=True)
    profile_picture = models.FileField(upload_to='profiles/', null=True, blank=True)
    preferred_language = models.CharField(
        max_length=5,
        choices=[('en', 'English'), ('am', 'Amharic')],
        default='en'
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = UserManager()

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.email

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    @property
    def is_taxpayer(self):
        return self.role == self.Role.TAXPAYER

    @property
    def is_tax_officer(self):
        return self.role == self.Role.TAX_OFFICER

    @property
    def is_super_admin(self):
        return self.role == self.Role.SUPER_ADMIN


class EmailVerification(models.Model):
    """Email verification tokens for user registration."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='email_verification')
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'email_verifications'
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f'{self.user.email} - {"Used" if self.is_used else "Pending"}'

    def is_valid(self):
        from django.utils import timezone
        return not self.is_used and self.expires_at > timezone.now()

    def save(self, *args, **kwargs):
        if not self.token:
            import secrets
            self.token = secrets.token_urlsafe(32)
        if not self.expires_at:
            from datetime import timedelta
            from django.utils import timezone
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)


class TwoFactorAuth(models.Model):
    """Two-Factor Authentication settings for users."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='two_factor_auth')
    is_enabled = models.BooleanField(default=False)
    secret_key = models.CharField(max_length=32, blank=True, null=True)
    backup_codes = models.JSONField(default=list, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'two_factor_auth'

    def __str__(self):
        return f'{self.user.email} - {"2FA Enabled" if self.is_enabled else "2FA Disabled"}'

    def generate_backup_codes(self):
        import secrets
        codes = [secrets.token_hex(4).upper() for _ in range(10)]
        self.backup_codes = codes
        self.save()
        return codes

    def verify_backup_code(self, code):
        if code.upper() in self.backup_codes:
            self.backup_codes.remove(code.upper())
            self.save()
            return True
        return False


class TaxProfile(models.Model):
    class TaxpayerType(models.TextChoices):
        INDIVIDUAL = 'individual', 'Individual'
        BUSINESS = 'business', 'Business'
        NGO = 'ngo', 'NGO / Non-Profit'

    class BusinessSector(models.TextChoices):
        TRADE = 'trade', 'Trade'
        MANUFACTURING = 'manufacturing', 'Manufacturing'
        SERVICE = 'service', 'Service'
        AGRICULTURE = 'agriculture', 'Agriculture'
        OTHER = 'other', 'Other'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='tax_profile')
    taxpayer_type = models.CharField(max_length=20, choices=TaxpayerType.choices, blank=True)
    business_name = models.CharField(max_length=200, null=True, blank=True)
    business_registration_number = models.CharField(max_length=50, null=True, blank=True)
    business_sector = models.CharField(max_length=30, choices=BusinessSector.choices, null=True, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, null=True, blank=True)
    national_id = models.CharField(max_length=50, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    is_vat_registered = models.BooleanField(default=False)
    vat_registration_date = models.DateField(null=True, blank=True)
    annual_turnover = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tax_profiles'

    def __str__(self):
        return f'{self.user.get_full_name()} - {self.taxpayer_type}'


class PasswordResetToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        db_table = 'password_reset_tokens'
