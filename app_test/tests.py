from django.test import TestCase
from django.test import override_settings
from django.urls import reverse


@override_settings(ROOT_URLCONF="app_test.test_urls")
class AppTestPagesTests(TestCase):
    def test_index_page_renders(self):
        response = self.client.get(reverse("app_test:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Démo des popups")
        self.assertContains(response, 'data-popup-demo="simple"')
        self.assertContains(response, 'data-popup-demo="long"')
        self.assertContains(response, "Popup sans bouton")
        self.assertContains(response, "Popup longue avec 4 boutons")

    def test_removed_mockup_routes_return_404(self):
        for path in [
            "/maquette-1/",
            "/maquette-2/",
            "/maquette-3/",
            "/maquette-4/",
            "/maquette-5/",
            "/v1/",
            "/v2/",
            "/v3/",
            "/v4/",
        ]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
