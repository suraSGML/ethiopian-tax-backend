from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from .models import User, TaxProfile, EmailVerification, TwoFactorAuth
from .utils import generate_tin


class TaxProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxProfile
        exclude = ['user']
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'taxpayer_type': {'required': False},
            'address': {'required': False, 'allow_blank': True},
            'city': {'required': False, 'allow_blank': True},
            'region': {'required': False, 'allow_blank': True},
            'business_name': {'required': False, 'allow_blank': True},
            'business_sector': {'required': False, 'allow_blank': True},
            'business_registration_number': {'required': False, 'allow_blank': True},
            'national_id': {'required': False, 'allow_blank': True},
            'date_of_birth': {'required': False, 'allow_null': True},
            'postal_code': {'required': False, 'allow_blank': True},
        }


class UserSerializer(serializers.ModelSerializer):
    tax_profile = TaxProfileSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'tin', 'phone', 'role', 'is_active', 'is_verified',
            'date_joined', 'last_login', 'profile_picture',
            'preferred_language', 'tax_profile'
        ]
        read_only_fields = ['id', 'tin', 'role', 'date_joined', 'last_login', 'is_verified']

    def get_full_name(self, obj):
        return obj.get_full_name()


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    tax_profile = TaxProfileSerializer(required=False)

    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name', 'phone',
            'password', 'confirm_password', 'preferred_language', 'tax_profile'
        ]

    def validate(self, attrs):
        email = attrs.get('email')
        if not email:
            raise serializers.ValidationError({'email': 'Email is required.'})
        
        password = attrs.get('password')
        if not password:
            raise serializers.ValidationError({'password': 'Password is required.'})
        if len(password) < 6:
            raise serializers.ValidationError({'password': 'Password must be at least 6 characters.'})
        
        confirm_password = attrs.get('confirm_password')
        if not confirm_password:
            raise serializers.ValidationError({'confirm_password': 'Please confirm your password.'})
        if password != confirm_password:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        
        # Check if email already exists
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError({'email': 'A user with this email already exists.'})
        
        # Handle empty phone string
        if attrs.get('phone') == '':
            attrs['phone'] = None
        
        attrs.pop('confirm_password')
        return attrs

    def create(self, validated_data):
        profile_data = validated_data.pop('tax_profile', None)
        
        # Set defaults for optional fields
        validated_data.setdefault('first_name', '')
        validated_data.setdefault('last_name', '')
        validated_data.setdefault('phone', None)
        validated_data.setdefault('preferred_language', 'en')
        
        user = User.objects.create_user(**validated_data)
        user.tin = generate_tin()
        user.save()
        
        # Only create tax_profile if it has meaningful data
        if profile_data:
            meaningful_data = {k: v for k, v in profile_data.items() if v not in [None, '', []]}
            if meaningful_data:
                meaningful_data.setdefault('taxpayer_type', 'individual')
                meaningful_data.setdefault('address', '')
                meaningful_data.setdefault('city', '')
                meaningful_data.setdefault('region', '')
                try:
                    TaxProfile.objects.create(user=user, **meaningful_data)
                except Exception:
                    pass
        
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['role'] = user.role
        token['full_name'] = user.get_full_name()
        token['tin'] = user.tin
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        data['user'] = UserSerializer(user).data
        return data


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    confirm_new_password = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_new_password']:
            raise serializers.ValidationError({'confirm_new_password': 'Passwords do not match.'})
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])
    confirm_password = serializers.CharField()

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        return attrs


class AdminUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone', 'role', 'password']

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class EmailVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailVerification
        fields = ['token', 'created_at', 'expires_at', 'is_used']
        read_only_fields = ['token', 'created_at', 'expires_at', 'is_used']


class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)

    def validate(self, attrs):
        token = attrs.get('token')
        try:
            verification = EmailVerification.objects.select_related('user').get(token=token)
        except EmailVerification.DoesNotExist:
            raise serializers.ValidationError({'token': 'Invalid verification token.'})
        
        if not verification.is_valid():
            raise serializers.ValidationError({'token': 'Verification token has expired or already used.'})
        
        attrs['verification'] = verification
        return attrs


class TwoFactorAuthSerializer(serializers.ModelSerializer):
    class Meta:
        model = TwoFactorAuth
        fields = ['is_enabled', 'verified_at']
        read_only_fields = ['is_enabled', 'verified_at']


class TwoFactorSetupSerializer(serializers.Serializer):
    pass  # Returns secret key and QR code data


class TwoFactorVerifySerializer(serializers.Serializer):
    code = serializers.CharField(required=True, min_length=6, max_length=6)
    
    def validate(self, attrs):
        code = attrs.get('code')
        if not code.isdigit():
            raise serializers.ValidationError({'code': 'Code must be 6 digits.'})
        return attrs


class TwoFactorDisableSerializer(serializers.Serializer):
    password = serializers.CharField(required=True)
