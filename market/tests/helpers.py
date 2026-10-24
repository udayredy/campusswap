import io
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from market.models import Course, Listing

User = get_user_model()
PASSWORD = "Str0ng-Passw0rd!"
TEMP_MEDIA = tempfile.mkdtemp(prefix="campusswap-test-media-")


def image_file(name="photo.jpg", size=(60, 40), color=(200, 30, 30)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")


@override_settings(MEDIA_ROOT=TEMP_MEDIA, STUDENT_EMAIL_DOMAINS=(".ca", ".edu"))
class CampusTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.course = Course.objects.create(code="comp1030", name="Intro to Programming", program="CP")
        cls.seller = User.objects.create_user("seller", "seller@college.ca", PASSWORD, first_name="Sam")
        cls.buyer = User.objects.create_user("buyer", "buyer@college.ca", PASSWORD, first_name="Bea")
        cls.other = User.objects.create_user("other", "other@college.ca", PASSWORD)
        cls.listing = Listing.objects.create(
            seller=cls.seller, course=cls.course, title="Starting Out with Python", price=45, isbn="9780136929734"
        )

    def login(self, user):
        self.client.force_login(user)
