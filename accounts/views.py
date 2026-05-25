from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import update_session_auth_hash
from django.utils import timezone
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view

from .models import User, TaxProfile, PasswordResetToken, EmailVerification, TwoFactorAuth
from .serializers import (
    UserSerializer, UserRegistrationSerializer, CustomTokenObtainPairSerializer,
    TaxProfileSerializer, ChangePasswordSerializer, PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer, AdminUserCreateSerializer, VerifyEmailSerializer,
    TwoFactorAuthSerializer, TwoFactorSetupSerializer, TwoFactorVerifySerializer, TwoFactorDisableSerializer
)
from .permissions import IsTaxOfficer, IsSuperAdmin, IsOwnerOrAdmin
from .utils import generate_reset_token, get_token_expiry
from notifications.tasks import send_welcome_email, send_password_reset_email, send_email_verification


class RegisterView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Create email verification token (with error handling)
        try:
            verification = EmailVerification.objects.create(user=user)
            send_email_verification.delay(str(user.id), verification.token)
        except Exception as e:
            # Log error but don't fail registration
            print(f"Email verification creation failed: {e}")
        
        # Send welcome email (with error handling)
        try:
            send_welcome_email.delay(str(user.id))
        except Exception as e:
            print(f"Welcome email failed: {e}")
        
        refresh = RefreshToken.for_user(user)
        return Response({
            'message': 'Registration successful. Your TIN has been assigned.',
            'tin': user.tin,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class LogoutView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({'message': 'Logged out successfully.'})
        except Exception:
            return Response({'error': 'Invalid token.'}, status=status.HTTP_400_BAD_REQUEST)


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class TaxProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = TaxProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        profile, _ = TaxProfile.objects.get_or_create(user=self.request.user)
        return profile


class ChangePasswordView(generics.GenericAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response({'error': 'Current password is incorrect.'}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response({'message': 'Password changed successfully.'})


class PasswordResetRequestView(generics.GenericAPIView):
    serializer_class = PasswordResetRequestSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        try:
            user = User.objects.get(email=email)
            token = generate_reset_token()
            PasswordResetToken.objects.create(
                user=user, token=token, expires_at=get_token_expiry()
            )
            send_password_reset_email.delay(str(user.id), token)
        except User.DoesNotExist:
            pass  # Don't reveal if email exists
        return Response({'message': 'If the email exists, a reset link has been sent.'})


class PasswordResetConfirmView(generics.GenericAPIView):
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token_str = serializer.validated_data['token']
        try:
            reset_token = PasswordResetToken.objects.get(
                token=token_str, is_used=False, expires_at__gt=timezone.now()
            )
        except PasswordResetToken.DoesNotExist:
            return Response({'error': 'Invalid or expired token.'}, status=status.HTTP_400_BAD_REQUEST)
        user = reset_token.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        reset_token.is_used = True
        reset_token.save()
        return Response({'message': 'Password reset successfully.'})


@extend_schema_view(
    list=extend_schema(summary='List all users (Admin only)'),
    retrieve=extend_schema(summary='Get user details'),
)
class UserManagementViewSet(viewsets.ModelViewSet):
    queryset = User.objects.select_related('tax_profile').all()
    permission_classes = [IsTaxOfficer]
    filterset_fields = ['role', 'is_active', 'is_verified']
    search_fields = ['email', 'first_name', 'last_name', 'tin']
    ordering_fields = ['date_joined', 'last_login']

    def get_serializer_class(self):
        if self.action == 'create':
            return AdminUserCreateSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action in ['destroy', 'create']:
            return [IsSuperAdmin()]
        return super().get_permissions()

    @action(detail=True, methods=['post'], permission_classes=[IsTaxOfficer])
    def toggle_active(self, request, pk=None):
        user = self.get_object()
        user.is_active = not user.is_active
        user.save()
        status_str = 'activated' if user.is_active else 'deactivated'
        return Response({'message': f'User {status_str} successfully.', 'is_active': user.is_active})

    @action(detail=True, methods=['post'], permission_classes=[IsTaxOfficer])
    def verify(self, request, pk=None):
        user = self.get_object()
        user.is_verified = True
        user.save()
        return Response({'message': 'User verified successfully.'})


class VerifyEmailView(generics.GenericAPIView):
    serializer_class = VerifyEmailSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        verification = serializer.validated_data['verification']
        
        # Mark as used and verify user
        verification.is_used = True
        verification.used_at = timezone.now()
        verification.save()
        
        user = verification.user
        user.is_verified = True
        user.save()
        
        return Response({
            'message': 'Email verified successfully.',
            'user': UserSerializer(user).data
        })


class ResendVerificationEmailView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.is_verified:
            return Response({'message': 'Email already verified.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Create new verification token
        EmailVerification.objects.filter(user=user).delete()
        verification = EmailVerification.objects.create(user=user)
        
        # Send verification email (task)
        try:
            from notifications.tasks import send_email_verification
            send_email_verification.delay(str(user.id), verification.token)
        except Exception:
            pass
        
        return Response({'message': 'Verification email sent successfully.'})


class TwoFactorAuthView(generics.RetrieveAPIView):
    serializer_class = TwoFactorAuthSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        two_fa, _ = TwoFactorAuth.objects.get_or_create(user=self.request.user)
        return two_fa


class TwoFactorSetupView(generics.GenericAPIView):
    serializer_class = TwoFactorSetupSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        import pyotp
        import qrcode
        import io
        import base64
        
        user = request.user
        two_fa, _ = TwoFactorAuth.objects.get_or_create(user=user)
        
        # Generate secret key
        secret = pyotp.random_base32()
        two_fa.secret_key = secret
        two_fa.is_enabled = False
        two_fa.save()
        
        # Generate QR code
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.email,
            issuer_name='Ethiopian Tax System'
        )
        
        qr = qrcode.make(provisioning_uri)
        buffer = io.BytesIO()
        qr.save(buffer, format='PNG')
        qr_code_data = base64.b64encode(buffer.getvalue()).decode()
        
        return Response({
            'message': '2FA setup initiated. Scan the QR code with your authenticator app.',
            'secret_key': secret,
            'qr_code': f'data:image/png;base64,{qr_code_data}',
            'manual_entry_key': secret
        })


class TwoFactorVerifyView(generics.GenericAPIView):
    serializer_class = TwoFactorVerifySerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        import pyotp
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data['code']
        
        user = request.user
        two_fa = get_object_or_404(TwoFactorAuth, user=user)
        
        if not two_fa.secret_key:
            return Response({'error': '2FA not set up. Please setup 2FA first.'}, status=status.HTTP_400_BAD_REQUEST)
        
        totp = pyotp.TOTP(two_fa.secret_key)
        if totp.verify(code):
            two_fa.is_enabled = True
            two_fa.verified_at = timezone.now()
            two_fa.generate_backup_codes()
            two_fa.save()
            
            return Response({
                'message': '2FA enabled successfully.',
                'backup_codes': two_fa.backup_codes
            })
        else:
            return Response({'error': 'Invalid code. Please try again.'}, status=status.HTTP_400_BAD_REQUEST)


class TwoFactorDisableView(generics.GenericAPIView):
    serializer_class = TwoFactorDisableSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        password = serializer.validated_data['password']
        
        user = request.user
        if not user.check_password(password):
            return Response({'error': 'Incorrect password.'}, status=status.HTTP_400_BAD_REQUEST)
        
        two_fa = get_object_or_404(TwoFactorAuth, user=user)
        two_fa.is_enabled = False
        two_fa.secret_key = None
        two_fa.backup_codes = []
        two_fa.save()
        
        return Response({'message': '2FA disabled successfully.'})
