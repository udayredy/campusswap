from django.contrib import admin
from django.db.models import Count, Q
from django.utils.html import format_html

from .models import Course, Favourite, Listing, ListingPhoto, Message, Report, Review

admin.site.site_header = "CampusSwap Moderation"
admin.site.site_title = "CampusSwap Admin"
admin.site.index_title = "Marketplace management"


class ListingPhotoInline(admin.TabularInline):
    model = ListingPhoto
    extra = 0
    fields = ("preview", "image", "position")
    readonly_fields = ("preview",)

    @admin.display(description="Preview")
    def preview(self, obj):
        if obj.pk and obj.image:
            return format_html('<img src="{}" style="height:60px;border-radius:6px">', obj.image.url)
        return "—"


class ReportInline(admin.TabularInline):
    model = Report
    extra = 0
    fields = ("reporter", "reason", "details", "status", "created_at")
    readonly_fields = ("reporter", "reason", "details", "created_at")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "program", "listing_count")
    list_filter = ("program",)
    search_fields = ("code", "name")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_n=Count("listings"))

    @admin.display(description="Listings", ordering="_n")
    def listing_count(self, obj):
        return obj._n


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("title", "seller", "course", "price", "condition", "status", "is_hidden", "open_reports", "created_at")
    list_filter = ("is_hidden", "status", "category", "condition", "course__program")
    search_fields = ("title", "description", "isbn", "course__code", "seller__username")
    list_editable = ("is_hidden",)
    autocomplete_fields = ("course",)
    raw_id_fields = ("seller",)
    inlines = [ListingPhotoInline, ReportInline]
    actions = ["hide_listings", "unhide_listings"]
    date_hierarchy = "created_at"

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _open=Count("reports", filter=Q(reports__status=Report.Status.OPEN))
        ).select_related("seller", "course")

    @admin.display(description="Open reports", ordering="_open")
    def open_reports(self, obj):
        if obj._open:
            return format_html('<b style="color:#c0392b">{}</b>', obj._open)
        return 0

    @admin.action(description="Hide selected listings")
    def hide_listings(self, request, queryset):
        self.message_user(request, f"Hid {queryset.update(is_hidden=True)} listing(s).")

    @admin.action(description="Un-hide selected listings")
    def unhide_listings(self, request, queryset):
        self.message_user(request, f"Restored {queryset.update(is_hidden=False)} listing(s).")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("listing", "reason", "reporter", "status", "listing_hidden", "created_at")
    list_filter = ("status", "reason")
    search_fields = ("listing__title", "reporter__username", "details")
    raw_id_fields = ("listing", "reporter")
    actions = ["resolve_and_hide", "dismiss_and_restore"]

    @admin.display(boolean=True, description="Listing hidden")
    def listing_hidden(self, obj):
        return obj.listing.is_hidden

    @admin.action(description="Resolve: hide the reported listing(s)")
    def resolve_and_hide(self, request, queryset):
        Listing.objects.filter(reports__in=queryset).update(is_hidden=True)
        n = queryset.update(status=Report.Status.RESOLVED)
        self.message_user(request, f"Resolved {n} report(s) and hid the listing(s).")

    @admin.action(description="Dismiss: report was unfounded, restore listing(s)")
    def dismiss_and_restore(self, request, queryset):
        listing_ids = list(queryset.values_list("listing_id", flat=True))
        n = queryset.update(status=Report.Status.DISMISSED)
        # Only restore listings that no longer have any open reports.
        Listing.objects.filter(pk__in=listing_ids).exclude(reports__status=Report.Status.OPEN).update(is_hidden=False)
        self.message_user(request, f"Dismissed {n} report(s).")


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("listing", "reviewer", "rating", "comment", "created_at")
    list_filter = ("rating",)
    search_fields = ("listing__title", "reviewer__username", "comment")
    raw_id_fields = ("listing", "reviewer")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("listing", "sender", "recipient", "short_body", "is_read", "sent_at")
    list_filter = ("is_read",)
    search_fields = ("body", "sender__username", "recipient__username")
    raw_id_fields = ("listing", "sender", "recipient")

    @admin.display(description="Message")
    def short_body(self, obj):
        return obj.body[:60]


@admin.register(Favourite)
class FavouriteAdmin(admin.ModelAdmin):
    list_display = ("user", "listing", "created_at")
    raw_id_fields = ("user", "listing")
