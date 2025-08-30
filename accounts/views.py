from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.views.generic import CreateView, TemplateView, UpdateView
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from tenants.models import Business

from .models import User, UserProfile

class LoginView(TemplateView):
    """View for user login."""
    template_name = 'accounts/login.html'
    
    def post(self, request, *args, **kwargs):
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        user = authenticate(request, email=email, password=password)
        
        if user is not None:
            login(request, user)
            
            # Redirect based on user type
            if user.is_business_admin and user.tenant_id:
                from tenants.models import Business
                try:
                    business = Business.objects.get(id=user.tenant_id)
                    return redirect('business_dashboard', slug=business.slug)
                except Business.DoesNotExist:
                    pass
            
            return redirect('home')
        else:
            messages.error(request, 'Invalid email or password.')
            return self.render_to_response(self.get_context_data())


class RegisterView(CreateView):
    """View for customer registration."""
    model = User
    template_name = 'accounts/register.html'
    fields = ['email', 'password', 'first_name', 'last_name', 'phone']
    success_url = reverse_lazy('login')
    
    def form_valid(self, form):
        user = form.save(commit=False)
        user.username = user.email
        user.set_password(form.cleaned_data['password'])
        user.is_customer = True
        user.is_business_admin = False
        user.save()
        
        # Create profile
        UserProfile.objects.create(user=user)
        
        messages.success(self.request, 'Account created successfully! Please log in.')
        return redirect(self.success_url)


@method_decorator(login_required, name='dispatch')
class ProfileUpdateView(UpdateView):
    """View for updating user profile."""
    model = UserProfile
    template_name = 'accounts/profile.html'
    fields = ['profile_picture', 'bio', 'date_of_birth', 'address', 'city', 'country']
    success_url = reverse_lazy('profile')
    
    def dispatch(self, request, *args, **kwargs):
        # Business admins should manage tenant settings, not customer profile
        if request.user.is_business_admin and request.user.tenant_id:
            try:
                business = Business.objects.get(id=request.user.tenant_id)
                return redirect('business_settings', slug=business.slug)
            except Business.DoesNotExist:
                pass
        return super().dispatch(request, *args, **kwargs)
    
    def get_object(self, queryset=None):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile
    
    def form_valid(self, form):
        messages.success(self.request, 'Profile updated successfully!')
        return super().form_valid(form)


class ForgotPasswordView(TemplateView):
    """Custom password recovery without email.

    Users enter phone and last name. If we find a matching account,
    we generate a short-lived signed token and redirect to a reset page.
    """
    template_name = 'accounts/forgot_password.html'

    def post(self, request, *args, **kwargs):
        phone = request.POST.get('phone', '').strip()
        last_name = request.POST.get('last_name', '').strip()

        if not phone or not last_name:
            messages.error(request, 'Please provide both phone and last name.')
            return self.render_to_response(self.get_context_data())

        qs = User.objects.filter(phone=phone, last_name__iexact=last_name)
        count = qs.count()
        if count == 0:
            messages.error(request, 'No matching account found. Please check your details.')
            return self.render_to_response(self.get_context_data())
        if count > 1:
            messages.error(request, 'Multiple accounts match these details. Please contact support.')
            return self.render_to_response(self.get_context_data())

        user = qs.first()
        signer = TimestampSigner()
        token = signer.sign(str(user.pk))
        return redirect('password_reset_custom', token=token)


class PasswordResetConfirmView(TemplateView):
    """Set a new password after verifying a signed token (no email flow)."""
    template_name = 'accounts/reset_password.html'
    token_max_age_seconds = 15 * 60  # 15 minutes

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['token'] = self.kwargs.get('token')
        return context

    def post(self, request, *args, **kwargs):
        password = request.POST.get('password')
        confirm = request.POST.get('confirm_password')
        token = kwargs.get('token')

        if not password or not confirm:
            messages.error(request, 'Please fill in both password fields.')
            return self.render_to_response(self.get_context_data())
        if password != confirm:
            messages.error(request, 'Passwords do not match.')
            return self.render_to_response(self.get_context_data())

        signer = TimestampSigner()
        try:
            user_pk = signer.unsign(token, max_age=self.token_max_age_seconds)
        except SignatureExpired:
            messages.error(request, 'The reset link has expired. Please try again.')
            return redirect('password_forgot')
        except BadSignature:
            messages.error(request, 'Invalid reset link.')
            return redirect('password_forgot')

        try:
            user = User.objects.get(pk=user_pk)
        except User.DoesNotExist:
            messages.error(request, 'Account not found.')
            return redirect('password_forgot')

        user.set_password(password)
        user.save()
        messages.success(request, 'Your password has been reset. You can now log in.')
        return redirect('login')