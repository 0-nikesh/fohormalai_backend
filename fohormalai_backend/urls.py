from django.urls import path
from core.views import MarketplacePostCreateView, NearbyPickupSchedulesView, PickupScheduleCreateView, SendOTPView, RegisterView, LoginView

urlpatterns = [
    path('api/send-otp/', SendOTPView.as_view()),
    path('api/register/', RegisterView.as_view()),
    path('api/login/', LoginView.as_view()),
    path('api/pickup-schedule/', PickupScheduleCreateView.as_view()),
    path('api/nearby-pickup-schedules/', NearbyPickupSchedulesView.as_view()),
    path('api/marketplace-post/', MarketplacePostCreateView.as_view()),
]
