import io

from locust import HttpUser, between, task


class LegalMetroLoadUser(HttpUser):
    wait_time = between(1, 3)
    token = None

    def on_start(self):
        """Authenticate user and obtain JWT access token."""
        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": "inspector@legalmetro.gov.in", "password": "InspectorPass123!"},
        )
        if response.status_code == 200:
            self.token = response.json().get("access_token")
        else:
            self.token = None

    @task(3)
    def check_health(self):
        """Verify system healthz probe under load."""
        self.client.get("/healthz")

    @task(2)
    def list_scans(self):
        """Fetch paginated scans list with auth headers."""
        if not self.token:
            return
        headers = {"Authorization": f"Bearer {self.token}"}
        self.client.get("/api/v1/scans?limit=20&offset=0", headers=headers)

    @task(1)
    def upload_scan(self):
        """Simulate concurrent multipart image uploads to /api/v1/scans."""
        if not self.token:
            return

        headers = {"Authorization": f"Bearer {self.token}"}

        # 1x1 transparent PNG file buffer
        dummy_png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
            b"\x00\x00\x00\x00IEND\xaeB`\x82"
        )

        files = [("images", ("sample_pack.png", io.BytesIO(dummy_png), "image/png"))]
        data = {
            "mode": "retail",
            "font_check_mode": "relative",
        }

        with self.client.post(
            "/api/v1/scans",
            headers=headers,
            data=data,
            files=files,
            catch_response=True,
        ) as response:
            # Expecting 202 Accepted for async enqueue, or 429 if rate-limited
            if response.status_code in [202, 429]:
                response.success()
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
