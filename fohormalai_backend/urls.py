from django.urls import path
from core.views import SendOTPView, RegisterView, LoginView

urlpatterns = [
    path('api/send-otp/', SendOTPView.as_view()),
    path('api/register/', RegisterView.as_view()),
    path('api/login/', LoginView.as_view()),
]
