from django.urls import reverse

from market.models import Listing

from .helpers import CampusTestCase


class SearchTests(CampusTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        Listing.objects.create(seller=cls.seller, title="TI-84 Calculator", price=85, category="ELEC", condition="GOOD")
        Listing.objects.create(seller=cls.seller, title="Cheap Lamp", price=5, category="FURN", condition="FAIR")
        Listing.objects.create(seller=cls.seller, title="Sold Book", price=20, status="SOLD")

    def titles(self, **params):
        r = self.client.get(reverse("market:browse"), params)
        self.assertEqual(r.status_code, 200)
        return [l.title for l in r.context["page"].object_list]

    def test_keyword(self):
        self.assertEqual(self.titles(q="calculator"), ["TI-84 Calculator"])

    def test_course_code_any_format(self):
        for q in ["COMP 1030", "comp1030", "COMP-1030"]:
            self.assertEqual(self.titles(q=q), ["Starting Out with Python"])

    def test_isbn_with_or_without_dashes(self):
        self.assertEqual(self.titles(q="978-0136929734"), ["Starting Out with Python"])
        self.assertEqual(self.titles(q="9780136929734"), ["Starting Out with Python"])

    def test_filters_and_sort(self):
        self.assertEqual(self.titles(category="ELEC"), ["TI-84 Calculator"])
        self.assertEqual(self.titles(condition="FAIR"), ["Cheap Lamp"])
        self.assertEqual(self.titles(min_price=10, max_price=50), ["Starting Out with Python"])
        self.assertEqual(self.titles(sort="price_asc")[0], "Cheap Lamp")
        self.assertEqual(self.titles(sort="price_desc")[0], "TI-84 Calculator")

    def test_sold_items_hidden_from_search(self):
        self.assertNotIn("Sold Book", self.titles())

    def test_garbage_input_never_crashes(self):
        for params in [{"min_price": "abc"}, {"sort": "drop table"}, {"page": "999"}, {"page": "x"}, {"category": "ZZZ"}, {"q": "%' OR 1=1"}]:
            with self.subTest(params=params):
                self.assertEqual(self.client.get(reverse("market:browse"), params).status_code, 200)

    def test_swapped_price_range_is_forgiven(self):
        self.assertEqual(self.titles(min_price=50, max_price=10), ["Starting Out with Python"])

    def test_sort_is_remembered_in_session(self):
        self.client.get(reverse("market:browse"), {"sort": "price_asc"})
        r = self.client.get(reverse("market:browse"))
        self.assertEqual(r.context["sort"], "price_asc")

    def test_course_finder_filters_by_program(self):
        r = self.client.get(reverse("market:course_finder"), {"program": "BUS"})
        self.assertEqual(list(r.context["courses"]), [])
        r = self.client.get(reverse("market:course_finder"), {"program": "CP"})
        self.assertEqual(len(r.context["courses"]), 1)
