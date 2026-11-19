from django.urls import path

from . import views

app_name = "bookings"

urlpatterns = [
    path("", views.home, name="home"),
    path("treatments/", views.services, name="services"),
    path("shop/", views.products, name="products"),
    path("policies/", views.policies, name="policies"),
    path("book/", views.book, name="book"),
    path("book/days/", views.days_partial, name="days"),
    path("book/slots/", views.slots_partial, name="slots"),
    path("booking/<str:token>/confirmed/", views.success, name="success"),
    path("booking/<str:token>/", views.manage, name="manage"),
    path("payments/stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/export/bookings.csv", views.export_bookings, name="export_bookings"),
    path("dashboard/export/services.csv", views.export_services, name="export_services"),
    path("health/", views.health, name="health"),
]
