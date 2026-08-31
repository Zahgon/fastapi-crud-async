import httpx
import pytest

from app.main import app


@pytest.fixture(scope="module")
def test_app():
    client = httpx.Client(app=app, base_url="http://testserver", follow_redirects=True)
    yield client  # testing happens here
