from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.LoginView.as_view(), name='login'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('profile/', views.ProfileUpdateView.as_view(), name='profile'),
    path('password/forgot/', views.ForgotPasswordView.as_view(), name='password_forgot'),
    path('password/reset/<str:token>/', views.PasswordResetConfirmView.as_view(), name='password_reset_custom'),
]