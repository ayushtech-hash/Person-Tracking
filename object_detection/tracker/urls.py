from django.urls import path
from tracker import views

urlpatterns = [
    path("", views.upload_video, name="upload_video"),
    path("detect_image/", views.detect_image, name="detect_image"),
    path("get_progress/", views.get_progress, name="get_progress"),
    path("generate-separate-video/",views.generate_separate_video,name="generate_separate_video",),
    path("merge-manual-identity-groups/", views.merge_manual_identity_groups, name="merge_manual_identity_groups"),
    path("undo-manual-identity-group-merge/", views.undo_manual_identity_group_merge, name="undo_manual_identity_group_merge"),
    path("dismiss-manual-grouping-suggestion/", views.dismiss_manual_grouping_suggestion, name="dismiss_manual_grouping_suggestion"),
    path("test-separate-video/",views.test_separate_video,name="test_separate_video",),
]
