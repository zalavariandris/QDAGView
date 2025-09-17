import pytest
import sys
from qtpy.QtWidgets import QApplication

pytest_plugins = ["pytestqt"]

@pytest.fixture(scope="session")
def qapp():
    """Create QApplication instance for Qt tests."""
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
    yield app
    # QApplication cleanup is handled automatically
