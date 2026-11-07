import base64
import io
import json
import tempfile
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from PIL import Image

from market import seed_catalog as cat
from market.management.commands import fetch_seed_images, seed_demo
from market.models import Listing, Message, Review

from .helpers import CampusTestCase

User = get_user_model()


def jpeg_bytes(color=(10, 120, 200), size=(300, 400)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG")
    return buf.getvalue()


class SeedCatalogTests(CampusTestCase):
    def test_catalog_is_consistent(self):
        codes = {c[0] for c in cat.COURSES}
        users = {s[0] for s in cat.STUDENTS}
        keys = [b[0] for b in cat.BOOKS] + [i[0] for i in cat.ITEMS]
        self.assertEqual(len(keys), len(set(keys)), "duplicate image keys")
        for b in cat.BOOKS:
            self.assertIn(b[1], codes)
            self.assertIn(b[7], users)
            self.assertRegex(b[4], r"^97[89]\d{10}$")
        for it in cat.ITEMS:
            self.assertIn(it[5], users)
            self.assertTrue(it[3] is None or it[3] in codes)

    def test_isbn13_check_digits_are_valid(self):
        for b in cat.BOOKS:
            digits = [int(d) for d in b[4]]
            total = sum(d * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits[:12]))
            self.assertEqual((10 - total % 10) % 10, digits[12], b[2])


class SeedCommandTests(CampusTestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        p1 = mock.patch.object(fetch_seed_images, "CACHE", self.tmp)
        p2 = mock.patch.object(seed_demo, "CACHE", self.tmp)
        p1.start(), p2.start()
        self.addCleanup(p1.stop)
        self.addCleanup(p2.stop)

    def test_offline_seed_creates_everything_with_fallback_covers(self):
        call_command("seed_demo", "--reset", "--offline", stdout=io.StringIO())
        self.assertEqual(Listing.objects.filter(seller__username__in=[s[0] for s in cat.STUDENTS]).count(), len(cat.BOOKS) + len(cat.ITEMS))
        self.assertTrue(all(l.photos.exists() for l in Listing.objects.filter(seller__username="priya_s")))
        self.assertTrue(Message.objects.exists())
        self.assertTrue(Review.objects.exists())
        # every review respects the app's own rule: reviewer messaged the seller first
        for r in Review.objects.all():
            self.assertTrue(Message.objects.filter(listing=r.listing, sender=r.reviewer).exists())

    def test_demo_passwords_work(self):
        call_command("seed_demo", "--reset", "--offline", stdout=io.StringIO())
        for username, *_rest in cat.STUDENTS:
            password = _rest[4]
            self.assertTrue(self.client.login(username=username, password=password), username)
        self.assertTrue(self.client.login(username="admin", password=cat.ADMIN[2]))
        mod = User.objects.get(username="mod_jordan")
        self.assertTrue(mod.is_staff and not mod.is_superuser)
        self.assertTrue(mod.has_perm("market.change_report"))

    def test_cached_images_are_used(self):
        (self.tmp / "pcc.jpg").write_bytes(jpeg_bytes())
        out = io.StringIO()
        call_command("seed_demo", "--reset", "--offline", stdout=out)
        self.assertIn("1 real photos", out.getvalue())

    def test_download_is_used_when_online(self):
        with mock.patch.object(seed_demo, "download", return_value=jpeg_bytes()) as dl:
            out = io.StringIO()
            call_command("seed_demo", "--reset", stdout=out)
        self.assertEqual(dl.call_count, len(cat.BOOKS) + len(cat.ITEMS))
        self.assertIn(f"{len(cat.BOOKS) + len(cat.ITEMS)} real photos", out.getvalue())

    def test_network_failure_falls_back_quickly(self):
        with mock.patch.object(seed_demo, "download", side_effect=OSError("no network")) as dl:
            call_command("seed_demo", "--reset", stdout=io.StringIO())
        self.assertEqual(dl.call_count, 1)  # stops trying after the first failure

    def test_import_browser_bundle(self):
        bundle = {
            "books": [{"isbn": cat.BOOKS[0][4], "jpg": base64.b64encode(jpeg_bytes()).decode()}],
            "items": [{"file": "File:" + cat.ITEMS[0][1], "jpg": base64.b64encode(jpeg_bytes()).decode()}],
        }
        f = self.tmp / "bundle.json"
        f.write_text(json.dumps(bundle))
        call_command("fetch_seed_images", "--from-bundle", str(f), stdout=io.StringIO())
        self.assertTrue((self.tmp / f"{cat.BOOKS[0][0]}.jpg").exists())
        self.assertTrue((self.tmp / f"{cat.ITEMS[0][0]}.jpg").exists())

    def test_credits_page(self):
        r = self.client.get("/credits/")
        self.assertContains(r, "Open Library")
        self.assertContains(r, "CC BY-SA 4.0")
        self.assertContains(r, cat.BOOKS[0][4])
