from django.core.exceptions import ValidationError
from django.db import IntegrityError

from market.models import Course, Listing, Report, Review, normalize_course_code, validate_isbn

from .helpers import CampusTestCase, User


class CourseCodeTests(CampusTestCase):
    def test_codes_are_normalised(self):
        for raw in ["comp1030", "COMP 1030", " comp-1030 ", "Comp  1030"]:
            self.assertEqual(normalize_course_code(raw), "COMP 1030")
        self.assertEqual(self.course.code, "COMP 1030")

    def test_course_code_unique(self):
        with self.assertRaises(IntegrityError):
            Course.objects.create(code="COMP 1030", name="dup", program="CP")


class ListingModelTests(CampusTestCase):
    def test_active_excludes_sold_and_hidden(self):
        sold = Listing.objects.create(seller=self.seller, title="Sold", price=1, status="SOLD")
        hidden = Listing.objects.create(seller=self.seller, title="Hidden", price=1, is_hidden=True)
        active = set(Listing.objects.active())
        self.assertIn(self.listing, active)
        self.assertNotIn(sold, active)
        self.assertNotIn(hidden, active)

    def test_price_bounds(self):
        bad = Listing(seller=self.seller, title="Too much", price=99999)
        with self.assertRaises(ValidationError):
            bad.full_clean()
        neg = Listing(seller=self.seller, title="Negative", price=-1)
        with self.assertRaises(ValidationError):
            neg.full_clean()

    def test_isbn_validator(self):
        validate_isbn("978-0-13-692973-9")
        validate_isbn("0-306-40615-X")
        with self.assertRaises(ValidationError):
            validate_isbn("12345")

    def test_profile_created_automatically(self):
        u = User.objects.create_user("fresh", "f@college.ca", "x")
        self.assertIsNotNone(u.profile)


class ReviewAndReportModelTests(CampusTestCase):
    def test_one_review_per_listing_per_buyer(self):
        Review.objects.create(listing=self.listing, reviewer=self.buyer, rating=5)
        with self.assertRaises(IntegrityError):
            Review.objects.create(listing=self.listing, reviewer=self.buyer, rating=4)

    def test_rating_check_constraint(self):
        with self.assertRaises(IntegrityError):
            Review.objects.create(listing=self.listing, reviewer=self.buyer, rating=9)

    def test_seller_average_rating(self):
        l2 = Listing.objects.create(seller=self.seller, title="Calculator", price=10)
        Review.objects.create(listing=self.listing, reviewer=self.buyer, rating=5)
        Review.objects.create(listing=l2, reviewer=self.other, rating=4)
        self.assertEqual(self.seller.profile.rating_summary(), {"avg": 4.5, "count": 2})

    def test_three_reports_auto_hide(self):
        reporters = [self.buyer, self.other, User.objects.create_user("third", "t@college.ca", "x")]
        for i, r in enumerate(reporters):
            Report.objects.create(listing=self.listing, reporter=r, reason="SCAM")
            self.listing.refresh_from_db()
            self.assertEqual(self.listing.is_hidden, i == 2)
