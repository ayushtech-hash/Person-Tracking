from django.urls import path
from tracker import views
from .api_views import RegisterAPIView, LoginAPIView, LogoutAPIView, RefreshAPIView, MeAPIView
from django.conf import settings

urlpatterns = [
    path("", views.upload_video, name="upload_video"),
    path("detect_image/", views.detect_image, name="detect_image"),
    path("get_progress/", views.get_progress, name="get_progress"),
    path("generate-separate-video/",views.generate_separate_video,name="generate_separate_video",),
    path("merge-selected-identity-groups/", views.merge_selected_identity_groups, name="merge_selected_identity_groups"),
    path("merge-manual-identity-groups/", views.merge_manual_identity_groups, name="merge_manual_identity_groups"),
    path("undo-manual-identity-group-merge/", views.undo_manual_identity_group_merge, name="undo_manual_identity_group_merge"),
    path("dismiss-manual-grouping-suggestion/", views.dismiss_manual_grouping_suggestion, name="dismiss_manual_grouping_suggestion"),
    path("test-separate-video/",views.test_separate_video,name="test_separate_video",),
]



urlpatterns += [
    # Pages (served as HTML)
    path('login/', views.login_page, name='login_page'),
    path('register/', views.register_page, name='register_page'),

    # JWT API (called by auth.js)
    path('api/auth/register/', RegisterAPIView.as_view(), name='api_register'),
    path('api/auth/login/', LoginAPIView.as_view(), name='api_login'),
    path('api/auth/logout/', LogoutAPIView.as_view(), name='api_logout'),
    path('api/auth/refresh/', RefreshAPIView.as_view(), name='api_refresh'),
    path('api/auth/me/', MeAPIView.as_view(), name='api_me'),
]
