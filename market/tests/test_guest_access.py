"""Guest (anonymous) vs member behaviour – the core of the 'guest page' requirement."""
from django.urls import reverse

from market.models import Favourite, Message

from .helpers import CampusTestCase


class GuestCanBrowseTests(CampusTestCase):
    def test_public_pages_open_to_guests(self):
        for url in [
            reverse("market:home"),
            reverse("market:browse"),
            reverse("market:guest_vs_member"),
            reverse("market:course_finder"),
            reverse("market:course_detail", args=[self.course.pk]),
            reverse("market:listing_detail", args=[self.listing.pk]),
            reverse("accounts:profile", args=["seller"]),
            reverse("accounts:signup"),
            reverse("accounts:login"),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_guest_sees_banner_and_gate(self):
        r = self.client.get(reverse("market:listing_detail", args=[self.listing.pk]))
        self.assertContains(r, "browsing as a guest")
        self.assertContains(r, "Sign up to contact seller")
        self.assertNotContains(r, 'name="body"')  # no message box for guests

    def test_member_sees_contact_form_not_banner(self):
        self.login(self.buyer)
        r = self.client.get(reverse("market:listing_detail", args=[self.listing.pk]))
        self.assertNotContains(r, "browsing as a guest")
        self.assertContains(r, "Contact seller")

    def test_recently_viewed_works_for_guests(self):
        self.client.get(reverse("market:listing_detail", args=[self.listing.pk]))
        self.assertEqual(self.client.session["recently_viewed"], [self.listing.pk])


class GuestIsRedirectedTests(CampusTestCase):
    def test_member_pages_redirect_to_login_with_next(self):
        for name, args in [
            ("market:listing_create", []),
            ("market:my_listings", []),
            ("market:favourites", []),
            ("market:inbox", []),
            ("market:report_create", [self.listing.pk]),
            ("market:conversation", [self.listing.pk, self.seller.pk]),
            ("accounts:profile_edit", []),
        ]:
            url = reverse(name, args=args)
            with self.subTest(url=url):
                r = self.client.get(url)
                self.assertEqual(r.status_code, 302)
                self.assertIn(reverse("accounts:login"), r["Location"])
                self.assertIn("next=", r["Location"])

    def test_guest_post_actions_do_nothing(self):
        self.client.post(reverse("market:favourite_toggle", args=[self.listing.pk]))
        self.client.post(reverse("market:conversation", args=[self.listing.pk, self.seller.pk]), {"body": "hi"})
        self.assertFalse(Favourite.objects.exists())
        self.assertFalse(Message.objects.exists())

    def test_ajax_favourite_returns_401_json_for_guest(self):
        r = self.client.post(reverse("market:favourite_toggle", args=[self.listing.pk]), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(r.status_code, 401)
        self.assertTrue(r.json()["login_required"])

    def test_friendly_message_explains_why(self):
        r = self.client.get(reverse("market:listing_create"), follow=True)
        self.assertContains(r, "Members only")
        self.assertContains(r, "post a listing")
