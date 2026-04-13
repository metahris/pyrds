from pyrds.api.main import app
from pyrds.sdk.client import PyrdsClient


def test_app_imports() -> None:
    assert app.title == "Pyrds"
    assert PyrdsClient is not None
