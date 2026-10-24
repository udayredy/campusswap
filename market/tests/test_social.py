from django.urls import reverse

from market.models import Favourite, Message, Report, Review

from .helpers import CampusTestCase


class FavouriteTests(CampusTestCase):
    def test_toggle(self):
        self.login(self.buyer)
        url = reverse("market:favourite_toggle", args=[self.listing.pk])
        r = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(r.json(), {"saved": True, "count": 1})
        r = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(r.json(), {"saved": False, "count": 0})

    def test_favourites_page(self):
        Favourite.objects.create(user=self.buyer, listing=self.listing)
        self.login(self.buyer)
        self.assertContains(self.client.get(reverse("market:favourites")), self.listing.title)


class MessagingTests(CampusTestCase):
    def convo_url(self, user):
        return reverse("market:conversation", args=[self.listing.pk, user.pk])

    def test_buyer_messages_seller_and_unread_badge(self):
        self.login(self.buyer)
        self.client.post(self.convo_url(self.seller), {"body": "Still available?"})
        m = Message.objects.get()
        self.assertEqual((m.sender, m.recipient), (self.buyer, self.seller))
        self.login(self.seller)
        r = self.client.get(reverse("market:inbox"))
        self.assertEqual(r.context["unread_count"], 1)
        self.client.get(self.convo_url(self.buyer))  # opening marks as read
        m.refresh_from_db()
        self.assertTrue(m.is_read)

    def test_cannot_message_non_seller_about_listing(self):
        self.login(self.buyer)
        r = self.client.post(self.convo_url(self.other), {"body": "hi"})
        self.assertEqual(r.status_code, 403)
        self.assertFalse(Message.objects.exists())

    def test_cannot_message_self(self):
        self.login(self.seller)
        self.client.post(self.convo_url(self.seller), {"body": "me"})
        self.assertFalse(Message.objects.exists())

    def test_empty_message_rejected(self):
        self.login(self.buyer)
        r = self.client.post(self.convo_url(self.seller), {"body": "   "})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Message.objects.exists())

    def test_third_party_cannot_read_thread(self):
        Message.objects.create(listing=self.listing, sender=self.buyer, recipient=self.seller, body="secret")
        self.login(self.other)
        r = self.client.get(self.convo_url(self.buyer))
        self.assertEqual(r.status_code, 403)


class ReviewTests(CampusTestCase):
    def test_must_have_messaged_before_reviewing(self):
        self.login(self.buyer)
        self.client.post(reverse("market:review_create", args=[self.listing.pk]), {"rating": 5})
        self.assertFalse(Review.objects.exists())
        Message.objects.create(listing=self.listing, sender=self.buyer, recipient=self.seller, body="hi")
        self.client.post(reverse("market:review_create", args=[self.listing.pk]), {"rating": 5, "comment": "Great"})
        self.assertEqual(Review.objects.get().rating, 5)

    def test_duplicate_review_handled_gracefully(self):
        Message.objects.create(listing=self.listing, sender=self.buyer, recipient=self.seller, body="hi")
        self.login(self.buyer)
        url = reverse("market:review_create", args=[self.listing.pk])
        self.client.post(url, {"rating": 5})
        r = self.client.post(url, {"rating": 1}, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Review.objects.count(), 1)

    def test_seller_cannot_review_self(self):
        self.login(self.seller)
        self.client.post(reverse("market:review_create", args=[self.listing.pk]), {"rating": 5})
        self.assertFalse(Review.objects.exists())

    def test_invalid_rating(self):
        Message.objects.create(listing=self.listing, sender=self.buyer, recipient=self.seller, body="hi")
        self.login(self.buyer)
        self.client.post(reverse("market:review_create", args=[self.listing.pk]), {"rating": 7})
        self.assertFalse(Review.objects.exists())


class ReportTests(CampusTestCase):
    def test_report_flow(self):
        self.login(self.buyer)
        url = reverse("market:report_create", args=[self.listing.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url, {"reason": "SCAM", "details": "asks for e-transfer first"})
        self.assertEqual(Report.objects.get().reporter, self.buyer)
        r = self.client.post(url, {"reason": "SCAM"}, follow=True)
        self.assertContains(r, "already reported")
        self.assertEqual(Report.objects.count(), 1)

    def test_cannot_report_own(self):
        self.login(self.seller)
        self.client.post(reverse("market:report_create", args=[self.listing.pk]), {"reason": "SCAM"})
        self.assertFalse(Report.objects.exists())
