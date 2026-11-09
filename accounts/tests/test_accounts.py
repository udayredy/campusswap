from django.core import mail
from django.urls import reverse

from accounts.forms import is_student_email
from market.tests.helpers import PASSWORD, CampusTestCase, User


class SignupTests(CampusTestCase):
    def data(self, **extra):
        d = {"first_name": "Nia", "last_name": "Lee", "username": "nia", "email": "Nia.Lee@Student.College.ca", "program": "CP", "password1": "Tr1cky-Pass-99", "password2": "Tr1cky-Pass-99", "agree": "on"}
        d.update(extra)
        return d

    def test_signup_creates_user_profile_and_logs_in(self):
        r = self.client.post(reverse("accounts:signup"), self.data())
        self.assertRedirects(r, reverse("market:home"))
        u = User.objects.get(username="nia")
        self.assertEqual(u.email, "nia.lee@student.college.ca")
        self.assertEqual(u.profile.program, "CP")
        self.assertEqual(int(self.client.session["_auth_user_id"]), u.pk)

    def test_signup_returns_to_next(self):
        nxt = reverse("market:listing_detail", args=[self.listing.pk])
        r = self.client.post(reverse("accounts:signup") + f"?next={nxt}", {**self.data(), "next": nxt})
        self.assertRedirects(r, nxt)

    def test_unsafe_next_ignored(self):
        r = self.client.post(reverse("accounts:signup"), {**self.data(), "next": "https://evil.example.com/"})
        self.assertRedirects(r, reverse("market:home"))

    def test_non_student_email_rejected(self):
        r = self.client.post(reverse("accounts:signup"), self.data(email="nia@gmail.com"))
        self.assertContains(r, "students only")
        self.assertFalse(User.objects.filter(username="nia").exists())

    def test_duplicate_email_and_username(self):
        r = self.client.post(reverse("accounts:signup"), self.data(email="BUYER@college.ca", username="Buyer"))
        errors = r.context["form"].errors
        self.assertIn("email", errors)
        self.assertIn("username", errors)

    def test_weak_and_mismatched_passwords(self):
        r = self.client.post(reverse("accounts:signup"), self.data(password1="12345678", password2="12345678"))
        self.assertIn("password2", r.context["form"].errors)
        r = self.client.post(reverse("accounts:signup"), self.data(password2="different-Pass-1"))
        self.assertIn("password2", r.context["form"].errors)

    def test_must_agree_and_pick_program(self):
        d = self.data()
        d.pop("agree")
        d["program"] = ""
        errors = self.client.post(reverse("accounts:signup"), d).context["form"].errors
        self.assertIn("agree", errors)
        self.assertIn("program", errors)

    def test_logged_in_user_redirected_away_from_signup(self):
        self.login(self.buyer)
        self.assertRedirects(self.client.get(reverse("accounts:signup")), reverse("market:home"))

    def test_email_domain_rule(self):
        self.assertTrue(is_student_email("a@georgebrown.ca"))
        self.assertTrue(is_student_email("a@mit.edu"))
        self.assertFalse(is_student_email("a@gmail.com"))
        self.assertFalse(is_student_email("a@evil.ca.com"))


class LoginTests(CampusTestCase):
    def test_login_with_username_or_email(self):
        for ident in ["buyer", "BUYER", "buyer@college.ca", "Buyer@College.ca"]:
            with self.subTest(ident=ident):
                self.client.logout()
                r = self.client.post(reverse("accounts:login"), {"username": ident, "password": PASSWORD})
                self.assertEqual(r.status_code, 302, ident)

    def test_wrong_password_friendly_error(self):
        r = self.client.post(reverse("accounts:login"), {"username": "buyer", "password": "nope"})
        self.assertContains(r, "don&#x27;t match")

    def test_inactive_user_cannot_login(self):
        User.objects.filter(pk=self.buyer.pk).update(is_active=False)
        r = self.client.post(reverse("accounts:login"), {"username": "buyer", "password": PASSWORD})
        self.assertEqual(r.status_code, 200)

    def test_login_redirects_to_next(self):
        nxt = reverse("market:listing_create")
        r = self.client.post(reverse("accounts:login"), {"username": "buyer", "password": PASSWORD, "next": nxt})
        self.assertRedirects(r, nxt)

    def test_logout_is_post(self):
        self.login(self.buyer)
        r = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(r, reverse("market:home"))
        self.assertNotIn("_auth_user_id", self.client.session)


class PasswordResetTests(CampusTestCase):
    def test_reset_email_sent(self):
        self.client.post(reverse("accounts:password_reset"), {"email": "buyer@college.ca"})
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/password/reset/", mail.outbox[0].body)


class ProfileTests(CampusTestCase):
    def test_public_profile_shows_listings(self):
        self.assertContains(self.client.get(reverse("accounts:profile", args=["seller"])), self.listing.title)

    def test_edit_profile(self):
        self.login(self.buyer)
        r = self.client.post(reverse("accounts:profile_edit"), {"first_name": "Bea", "last_name": "Z", "program": "BUS", "bio": "hello"})
        self.assertRedirects(r, reverse("accounts:profile", args=["buyer"]))
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.profile.program, "BUS")

    def test_unknown_profile_404(self):
        self.assertEqual(self.client.get(reverse("accounts:profile", args=["ghost"])).status_code, 404)
