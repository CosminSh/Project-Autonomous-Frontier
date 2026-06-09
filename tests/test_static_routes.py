from fastapi.testclient import TestClient
from pathlib import Path

from main import app


client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_route_serves_current_frontend_entrypoint():
    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "TERMINAL FRONTIER" in response.text
    assert response.headers["cache-control"] == "no-cache, no-store, must-revalidate"


def test_tracked_legacy_demo_entrypoints_stay_removed():
    stale_paths = [
        ROOT / "backend" / "scripts" / "demo_app.py",
        ROOT / "backend" / "scripts" / "main_demo.py",
        ROOT / "frontend" / "old_index.html",
    ]

    assert all(not path.exists() for path in stale_paths)


def test_admin_route_serves_operations_dashboard():
    response = client.get("/admin")

    assert response.status_code == 200
    assert "Terminal Frontier Admin" in response.text
    assert response.headers["cache-control"] == "no-cache, no-store, must-revalidate"


def test_frontend_uses_local_tailwind_bundle():
    html_files = [
        ROOT / "frontend" / "index.html",
        ROOT / "frontend" / "tutorial.html",
        ROOT / "frontend" / "about.html",
    ]

    for path in html_files:
        content = path.read_text(encoding="utf-8")
        assert "cdn.tailwindcss.com" not in content
        assert "tailwind.generated.css" in content
    assert (ROOT / "frontend" / "tailwind.generated.css").exists()
