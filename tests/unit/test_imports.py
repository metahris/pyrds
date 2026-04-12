from pyrds.api.main import app
from pyrds.sdk.client import PyrdsClient


def test_app_imports() -> None:
    assert app.title == "pyrds API"
    assert PyrdsClient is not None
