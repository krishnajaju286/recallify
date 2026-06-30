from django.urls import path
from . import views

urlpatterns = [
    # Landing Page
    path('', views.landing_view, name='landing'),
    
    # Auth
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    
    # Core Dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('create/', views.create_reminder, name='create_reminder'),
    path('edit/<int:pk>/', views.edit_reminder, name='edit_reminder'),
    path('delete/<int:pk>/', views.delete_reminder, name='delete_reminder'),
    
    # Features
    path('email-simulator/', views.email_sim_view, name='email_simulator'),
    path('history/', views.history_view, name='history'),
    path('subscription/', views.subscription_view, name='subscription'),
    path('settings/', views.settings_view, name='settings'),
]
