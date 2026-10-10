import re
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse

from accounts.models import Program

User = settings.AUTH_USER_MODEL

_CODE_RE = re.compile(r"^\s*([A-Za-z]{2,5})\s*-?\s*(\d{3,5}[A-Za-z]?)\s*$")


def normalize_course_code(raw: str) -> str:
    """'comp1030', 'COMP-1030' and ' comp 1030 ' all become 'COMP 1030'."""
    m = _CODE_RE.match(raw or "")
    if not m:
        return (raw or "").strip().upper()
    return f"{m.group(1).upper()} {m.group(2).upper()}"


def validate_isbn(value):
    digits = re.sub(r"[\s-]", "", value or "")
    if digits and not re.fullmatch(r"\d{9}[\dXx]|\d{13}", digits):
        raise ValidationError("ISBN must be 10 or 13 digits (dashes and spaces are fine).")


class Course(models.Model):
    code = models.CharField(max_length=12, unique=True, help_text="e.g. COMP 1030")
    name = models.CharField(max_length=120)
    program = models.CharField(max_length=5, choices=Program.choices)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} – {self.name}"

    def save(self, *args, **kwargs):
        self.code = normalize_course_code(self.code)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("market:course_detail", args=[self.pk])


class ListingQuerySet(models.QuerySet):
    def visible(self):
        """Not hidden by moderation."""
        return self.filter(is_hidden=False)

    def active(self):
        """What appears in browse/search: visible and still for sale."""
        return self.visible().filter(status=Listing.Status.AVAILABLE)


class Listing(models.Model):
    class Condition(models.TextChoices):
        NEW = "NEW", "New"
        GOOD = "GOOD", "Good"
        FAIR = "FAIR", "Fair"

    class Category(models.TextChoices):
        TEXTBOOKS = "BOOK", "Textbooks"
        ELECTRONICS = "ELEC", "Calculators & Electronics"
        SUPPLIES = "SUPP", "Lab & School Supplies"
        FURNITURE = "FURN", "Furniture & Dorm"
        CLOTHING = "CLTH", "Clothing & Uniforms"
        OTHER = "OTHR", "Other"

    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        SOLD = "SOLD", "Sold"

    CATEGORY_ICONS = {
        "BOOK": "bi-book",
        "ELEC": "bi-calculator",
        "SUPP": "bi-pencil-square",
        "FURN": "bi-lamp",
        "CLTH": "bi-bag",
        "OTHR": "bi-box-seam",
    }

    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name="listings")
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name="listings")
    title = models.CharField(max_length=120)
    description = models.TextField(max_length=2000, blank=True)
    price = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("5000.00"))],
        help_text="Enter 0 to give it away for free.",
    )
    condition = models.CharField(max_length=4, choices=Condition.choices, default=Condition.GOOD)
    category = models.CharField(max_length=4, choices=Category.choices, default=Category.TEXTBOOKS)
    isbn = models.CharField("ISBN", max_length=17, blank=True, validators=[validate_isbn])
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.AVAILABLE)
    is_hidden = models.BooleanField(default=False, help_text="Hidden by a moderator; not shown to anyone but the seller.")
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ListingQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "is_hidden", "-created_at"])]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("market:listing_detail", args=[self.pk])

    @property
    def is_sold(self):
        return self.status == self.Status.SOLD

    @property
    def is_free(self):
        return self.price == 0

    @property
    def icon(self):
        return self.CATEGORY_ICONS.get(self.category, "bi-box-seam")

    @property
    def cover(self):
        # Uses prefetched photos when available (no extra query in list views).
        photos = list(self.photos.all())
        return photos[0] if photos else None


def listing_photo_path(instance, filename):
    return f"listings/{instance.listing_id}/{filename}"


class ListingPhoto(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to=listing_photo_path)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return f"Photo {self.position + 1} of {self.listing}"


class Favourite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="favourites")
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="favourited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["user", "listing"], name="unique_favourite")]

    def __str__(self):
        return f"{self.user} ♥ {self.listing}"


class Message(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_messages")
    body = models.TextField(max_length=1000)
    sent_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["sent_at"]

    def __str__(self):
        return f"{self.sender} → {self.recipient}: {self.body[:30]}"

    def clean(self):
        if self.sender_id and self.sender_id == self.recipient_id:
            raise ValidationError("You can't message yourself.")


class Review(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews_written")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["listing", "reviewer"], name="one_review_per_buyer_per_listing"),
            models.CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5), name="rating_1_to_5"),
        ]

    def __str__(self):
        return f"{self.rating}★ by {self.reviewer} on {self.listing}"

    @property
    def seller(self):
        return self.listing.seller


class Report(models.Model):
    class Reason(models.TextChoices):
        SCAM = "SCAM", "Scam or fraud"
        PROHIBITED = "PROH", "Prohibited or unsafe item"
        MISLEADING = "MISL", "Misleading description or photos"
        OFFENSIVE = "OFFN", "Offensive content"
        OTHER = "OTHR", "Something else"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        RESOLVED = "RESOLVED", "Resolved – action taken"
        DISMISSED = "DISMISSED", "Dismissed"

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reports_filed")
    reason = models.CharField(max_length=4, choices=Reason.choices)
    details = models.TextField(max_length=500, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["listing", "reporter"], name="one_report_per_user_per_listing")]

    def __str__(self):
        return f"Report on {self.listing} ({self.get_reason_display()})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Community safety net: enough independent reports hide the listing until an admin looks.
        open_count = Report.objects.filter(listing=self.listing, status=self.Status.OPEN).count()
        if open_count >= settings.AUTO_HIDE_REPORT_THRESHOLD and not self.listing.is_hidden:
            Listing.objects.filter(pk=self.listing_id).update(is_hidden=True)
