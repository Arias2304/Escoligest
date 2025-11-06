from rest_framework.routers import DefaultRouter

from .views import (
    AppointmentViewSet,
    CalendarOptionViewSet,
    PatientActivityViewSet,
)

router = DefaultRouter()
router.register(r"activities", PatientActivityViewSet, basename="patient-activity")
router.register(r"calendar-options", CalendarOptionViewSet, basename="calendar-option")
router.register(r"", AppointmentViewSet, basename="appointment")

urlpatterns = router.urls
