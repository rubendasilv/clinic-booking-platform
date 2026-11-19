from django.contrib import admin, messages
from django.utils import timezone

from .analytics import bookings_csv_response
from .models import Booking, ClosedDay, Customer, OpeningHours, Product, Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "price",
        "price_is_from",
        "deposit",
        "duration_minutes",
        "buffer_minutes",
        "is_active",
        "display_order",
    )
    list_editable = ("price", "deposit", "is_active", "display_order")
    list_filter = ("category", "is_active")
    search_fields = ("name", "summary")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "stock", "is_active", "display_order")
    list_editable = ("price", "stock", "is_active", "display_order")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(OpeningHours)
class OpeningHoursAdmin(admin.ModelAdmin):
    list_display = ("weekday", "is_closed", "opens_at", "closes_at")
    list_editable = ("is_closed", "opens_at", "closes_at")


@admin.register(ClosedDay)
class ClosedDayAdmin(admin.ModelAdmin):
    list_display = ("date", "reason")
    date_hierarchy = "date"


class BookingInline(admin.TabularInline):
    model = Booking
    extra = 0
    fields = ("start", "service", "status", "deposit_paid")
    readonly_fields = fields
    show_change_link = True
    can_delete = False


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "phone", "marketing_opt_in", "created_at")
    search_fields = ("first_name", "last_name", "email", "phone")
    list_filter = ("marketing_opt_in",)
    inlines = [BookingInline]


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "start",
        "customer",
        "service",
        "status",
        "price",
        "deposit_paid",
        "source",
        "utm_source",
    )
    list_filter = ("status", "service__category", "service", "deposit_paid", "source", "utm_source")
    search_fields = ("customer__first_name", "customer__last_name", "customer__email")
    date_hierarchy = "start"
    autocomplete_fields = ("customer",)
    list_select_related = ("customer", "service")
    readonly_fields = (
        "end",
        "blocks_until",
        "price",
        "reminder_sent_at",
        "cancelled_at",
        "created_at",
        "updated_at",
        "stripe_session_id",
        "manage_link",
    )
    actions = ["mark_completed", "mark_no_show", "export_csv"]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # phone/walk-in bookings added by staff still get the confirmation email
        if not change and obj.status == Booking.Status.CONFIRMED:
            from django.db import transaction

            from .tasks import send_booking_confirmation

            transaction.on_commit(lambda: send_booking_confirmation.delay(obj.pk))

    @admin.display(description="Client's manage link")
    def manage_link(self, obj):
        return obj.get_manage_url() if obj.pk else "-"

    @admin.action(description="Mark selected as completed")
    def mark_completed(self, request, queryset):
        n = queryset.update(status=Booking.Status.COMPLETED)
        self.message_user(request, f"{n} booking(s) marked completed.", messages.SUCCESS)

    @admin.action(description="Mark selected as no-show")
    def mark_no_show(self, request, queryset):
        n = queryset.filter(start__lt=timezone.now()).update(status=Booking.Status.NO_SHOW)
        self.message_user(request, f"{n} past booking(s) marked no-show.", messages.SUCCESS)

    @admin.action(description="Export selected to CSV")
    def export_csv(self, request, queryset):
        return bookings_csv_response(queryset)
