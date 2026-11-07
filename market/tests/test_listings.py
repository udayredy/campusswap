from django.urls import reverse

from market.models import Listing, ListingPhoto

from .helpers import CampusTestCase, image_file


class ListingCrudTests(CampusTestCase):
    def post_data(self, **extra):
        data = {"title": "Calculus, 8th Ed.", "category": "BOOK", "condition": "GOOD", "price": "30", "course_code": "comp 1030", "isbn": "", "description": "Nice"}
        data.update(extra)
        return data

    def test_create_with_photos(self):
        self.login(self.seller)
        r = self.client.post(reverse("market:listing_create"), {**self.post_data(), "photos": [image_file("a.jpg"), image_file("b.jpg")]})
        listing = Listing.objects.get(title="Calculus, 8th Ed.")
        self.assertRedirects(r, listing.get_absolute_url())
        self.assertEqual(listing.course, self.course)
        self.assertEqual(listing.photos.count(), 2)

    def test_max_five_photos(self):
        self.login(self.seller)
        photos = [image_file(f"{i}.jpg") for i in range(6)]
        r = self.client.post(reverse("market:listing_create"), {**self.post_data(), "photos": photos})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Max 5 photos")
        self.assertFalse(Listing.objects.filter(title="Calculus, 8th Ed.").exists())

    def test_non_image_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.login(self.seller)
        fake = SimpleUploadedFile("virus.jpg", b"not an image", content_type="image/jpeg")
        r = self.client.post(reverse("market:listing_create"), {**self.post_data(), "photos": [fake]})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["form"].errors.get("photos"))

    def test_unknown_course_code_is_friendly_error(self):
        self.login(self.seller)
        r = self.client.post(reverse("market:listing_create"), self.post_data(course_code="XYZ 9999"))
        self.assertContains(r, "couldn&#x27;t find")

    def test_validation_errors(self):
        self.login(self.seller)
        r = self.client.post(reverse("market:listing_create"), self.post_data(title="", price="-4", isbn="123"))
        errors = r.context["form"].errors
        self.assertIn("title", errors)
        self.assertIn("price", errors)
        self.assertIn("isbn", errors)

    def test_edit_own_listing(self):
        self.login(self.seller)
        r = self.client.post(reverse("market:listing_edit", args=[self.listing.pk]), self.post_data(title="Updated title", price="40"))
        self.assertRedirects(r, self.listing.get_absolute_url())
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.title, "Updated title")

    def test_cannot_edit_or_delete_someone_elses(self):
        self.login(self.buyer)
        self.assertEqual(self.client.get(reverse("market:listing_edit", args=[self.listing.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("market:listing_delete", args=[self.listing.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("market:listing_toggle_sold", args=[self.listing.pk])).status_code, 404)
        self.assertTrue(Listing.objects.filter(pk=self.listing.pk).exists())

    def test_mark_sold_and_relist(self):
        self.login(self.seller)
        url = reverse("market:listing_toggle_sold", args=[self.listing.pk])
        self.client.post(url)
        self.listing.refresh_from_db()
        self.assertTrue(self.listing.is_sold)
        self.client.post(url)
        self.listing.refresh_from_db()
        self.assertFalse(self.listing.is_sold)

    def test_toggle_sold_requires_post(self):
        self.login(self.seller)
        self.assertEqual(self.client.get(reverse("market:listing_toggle_sold", args=[self.listing.pk])).status_code, 405)

    def test_delete_confirm_then_delete(self):
        self.login(self.seller)
        url = reverse("market:listing_delete", args=[self.listing.pk])
        self.assertContains(self.client.get(url), "Yes, delete")
        self.client.post(url)
        self.assertFalse(Listing.objects.filter(pk=self.listing.pk).exists())

    def test_photo_delete_owner_only(self):
        photo = ListingPhoto.objects.create(listing=self.listing, image=image_file())
        self.login(self.buyer)
        self.assertEqual(self.client.post(reverse("market:photo_delete", args=[photo.pk])).status_code, 404)
        self.login(self.seller)
        self.client.post(reverse("market:photo_delete", args=[photo.pk]))
        self.assertFalse(ListingPhoto.objects.filter(pk=photo.pk).exists())

    def test_hidden_listing_404_for_public_visible_to_owner(self):
        Listing.objects.filter(pk=self.listing.pk).update(is_hidden=True)
        url = reverse("market:listing_detail", args=[self.listing.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.login(self.seller)
        self.assertContains(self.client.get(url), "hidden by moderators")

    def test_view_count_not_incremented_by_owner(self):
        url = reverse("market:listing_detail", args=[self.listing.pk])
        self.client.get(url)
        self.login(self.seller)
        self.client.get(url)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.view_count, 1)
