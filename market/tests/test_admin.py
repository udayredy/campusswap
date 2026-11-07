from django.urls import reverse

from market.models import Listing, Report

from .helpers import CampusTestCase, User


class AdminModerationTests(CampusTestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("boss", "boss@college.ca", "x")
        self.client.force_login(self.admin)

    def test_admin_pages_load(self):
        for url in ["/admin/", "/admin/market/listing/", "/admin/market/report/", "/admin/auth/user/", "/admin/market/course/", "/admin/market/review/", "/admin/market/message/", f"/admin/market/listing/{self.listing.pk}/change/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_resolve_report_hides_listing(self):
        rep = Report.objects.create(listing=self.listing, reporter=self.buyer, reason="SCAM")
        self.client.post(reverse("admin:market_report_changelist"), {"action": "resolve_and_hide", "_selected_action": [rep.pk]})
        self.listing.refresh_from_db()
        rep.refresh_from_db()
        self.assertTrue(self.listing.is_hidden)
        self.assertEqual(rep.status, Report.Status.RESOLVED)

    def test_dismiss_report_restores_listing(self):
        Listing.objects.filter(pk=self.listing.pk).update(is_hidden=True)
        rep = Report.objects.create(listing=self.listing, reporter=self.buyer, reason="OTHR")
        self.client.post(reverse("admin:market_report_changelist"), {"action": "dismiss_and_restore", "_selected_action": [rep.pk]})
        self.listing.refresh_from_db()
        self.assertFalse(self.listing.is_hidden)

    def test_non_staff_blocked_from_admin(self):
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get("/admin/").status_code, 302)
