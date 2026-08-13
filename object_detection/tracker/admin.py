from django.contrib import admin

from .models import PersonTrackStats, TrackingReport


class PersonTrackStatsInline(admin.TabularInline):
    model = PersonTrackStats
    extra = 0


@admin.register(TrackingReport)
class TrackingReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "output_video",
        "peak_persons_detected",
        "total_visible_time",
        "selected_track_id",
        "created_at",
    )
    inlines = [PersonTrackStatsInline]


@admin.register(PersonTrackStats)
class PersonTrackStatsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "report",
        "track_id",
        "first_seen",
        "last_seen",
        "visible_duration",
        "frames_seen",
    )
