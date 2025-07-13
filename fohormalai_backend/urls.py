from django.urls import path
from core.views import (
    AdminCollectionHeatmapView, AdminDashboardStatsView, AdminDashboardView, 
    AdminDashboardActivitiesView, AdminAnalyticsView, AdminUsersListView,
    AdminPickupSchedulesUsersInRadiusView, AdminPickupSchedulesListView,
    BulkCollectionRequestUpdateView, CollectionRequestCreateView, CollectionRequestListView, 
    CollectionRequestStatusUpdateView, MarketplacePostCreateView, MarketplacePostListView, 
    NearbyPickupSchedulesView, PickupScheduleCreateView, PickupScheduleListView, 
    PickupScheduleUpdateView, SendOTPView, RegisterView, LoginView, UserNotificationsView,
    UserCollectionRequestsView, UserPickupSchedulesView, UserProfileView, ActivePickupsView,
    AdminAnalyticsPerformanceView, AdminAnalyticsWasteTrendsView, AdminAnalyticsWasteDistributionView,
    AdminAnalyticsLocationStatsView, AdminAnalyticsUserEngagementView, UserDetailsView
)

urlpatterns = [
    path('api/send-otp/', SendOTPView.as_view()),
    path('api/register/', RegisterView.as_view()),
    path('api/login/', LoginView.as_view()),
    
    # Pickup Schedule Management
    path('api/pickup-schedule/', PickupScheduleCreateView.as_view()),
    path('api/get-pickup-schedules/', PickupScheduleListView.as_view()),
    path('api/pickup-schedule/<str:schedule_id>/status/', PickupScheduleUpdateView.as_view()),
    path('api/nearby-pickup-schedules/', NearbyPickupSchedulesView.as_view()),
    
    # Admin Pickup Schedule Management
    path('api/admin/pickup-schedules/', AdminPickupSchedulesListView.as_view()),
    path('api/admin/pickup-schedules/users-in-radius/', AdminPickupSchedulesUsersInRadiusView.as_view()),
    path('api/admin/get-all-pickup-schedules/', AdminPickupSchedulesListView.as_view()),  # Alias for clearer API naming
    
    # Marketplace Management
    path('api/marketplace-post/', MarketplacePostCreateView.as_view()),
    path('api/get-marketplace-post/', MarketplacePostListView.as_view()),

    path('api/active-pickups/', ActivePickupsView.as_view()),
    
    # Collection Request Management
    path('api/collection-request/', CollectionRequestCreateView.as_view()),
    path('api/get-collection-request/', CollectionRequestListView.as_view()),
    path('api/user-collection-requests/', UserCollectionRequestsView.as_view()),
    path('api/user-collection-requests/<str:user_email>/', UserCollectionRequestsView.as_view()),
    path('api/collection-request/<str:request_id>/status/', CollectionRequestStatusUpdateView.as_view()),
    
    # Admin Features
    path('api/admin/collection-heatmap/', AdminCollectionHeatmapView.as_view()),
    path('api/admin/bulk-update-collections/', BulkCollectionRequestUpdateView.as_view()),
    path('api/admin/dashboard-stats/', AdminDashboardStatsView.as_view()),
    path('api/admin/dashboard/', AdminDashboardView.as_view()),
    path('api/admin/dashboard/stats/', AdminDashboardStatsView.as_view()),
    path('api/admin/dashboard/activities/', AdminDashboardActivitiesView.as_view()),
    path('api/admin/analytics/', AdminAnalyticsView.as_view()),
    path('api/admin/users/', AdminUsersListView.as_view()),
    
    # User Notifications & Personal Data
    path('api/user/notifications/', UserNotificationsView.as_view()),
    path('api/user/pickup-schedules/', UserPickupSchedulesView.as_view()),
    path('api/user/me/', UserProfileView.as_view()),
    path('api/user/info/',UserDetailsView.as_view()),
    
    # Admin Analytics
    path('api/admin/analytics/performance/', AdminAnalyticsPerformanceView.as_view()),
    path('api/admin/analytics/waste-trends/', AdminAnalyticsWasteTrendsView.as_view()),
    path('api/admin/analytics/waste-distribution/', AdminAnalyticsWasteDistributionView.as_view()),
    path('api/admin/analytics/location-stats/', AdminAnalyticsLocationStatsView.as_view()),
    path('api/admin/analytics/user-engagement/', AdminAnalyticsUserEngagementView.as_view()),
]
