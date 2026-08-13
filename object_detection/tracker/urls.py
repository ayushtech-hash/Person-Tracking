from django.urls import path
from tracker import views

urlpatterns = [
    path("", views.upload_video, name="upload_video"),
    path("detect_image/", views.detect_image, name="detect_image"),
    path("get_progress/", views.get_progress, name="get_progress"),
]

