from django.test import SimpleTestCase


class ServiceTests(SimpleTestCase):
    def test_orders(self):
        r = self.client.get("/orders")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 2)

    def test_probes_work_with_pod_ip_host_header(self):
        for path in ("/healthz", "/ready"):
            r = self.client.get(path, HTTP_HOST="10.1.2.3")
            self.assertEqual(r.status_code, 200)

    def test_unknown_host_rejected_for_real_endpoints(self):
        r = self.client.get("/orders", HTTP_HOST="evil.example.com")
        self.assertEqual(r.status_code, 400)
