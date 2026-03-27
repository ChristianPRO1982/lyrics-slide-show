from django.test import TestCase
from django.urls import reverse
from django.test import override_settings


@override_settings(ROOT_URLCONF="app_test.test_urls")
class AppTestPagesTests(TestCase):
    def test_index_page_renders(self):
        response = self.client.get(reverse("app_test:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "5 maquettes")
        self.assertContains(response, "Lumiere Sur Nos Pas")

    def test_mockup_pages_render(self):
        for route_name in [
            "app_test:mockup_1",
            "app_test:mockup_2",
            "app_test:mockup_3",
            "app_test:mockup_4",
            "app_test:mockup_5",
            "app_test:mockup_v1",
            "app_test:mockup_v2",
            "app_test:mockup_v3",
        ]:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                expected = "Base generique" if route_name == "app_test:mockup_v3" else "Recherche"
                self.assertContains(response, expected)

    def test_query_filters_song_list(self):
        response = self.client.get(reverse("app_test:mockup_3"), {"q": "harbor"})

        self.assertContains(response, "Anchor Over Tides")
        self.assertContains(response, "Silent Harbor Hymn")
        self.assertNotContains(response, "Lumiere Sur Nos Pas")
