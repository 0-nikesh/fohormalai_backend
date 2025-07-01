from django.urls import path
from core.views import CollectionRequestCreateView, MarketplacePostCreateView, MarketplacePostListView, NearbyPickupSchedulesView, PickupScheduleCreateView, SendOTPView, RegisterView, LoginView

urlpatterns = [
    path('api/send-otp/', SendOTPView.as_view()),
    path('api/register/', RegisterView.as_view()),
    path('api/login/', LoginView.as_view()),
    path('api/pickup-schedule/', PickupScheduleCreateView.as_view()),
    path('api/nearby-pickup-schedules/', NearbyPickupSchedulesView.as_view()),
    path('api/marketplace-post/', MarketplacePostCreateView.as_view()),
    path('api/get-marketplace-post/', MarketplacePostListView.as_view()),
    path('api/collection-request/', CollectionRequestCreateView.as_view()),
]
