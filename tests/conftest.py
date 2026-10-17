"""Share one native Tk interpreter across GUI regression tests."""
import pytest
from tkinterdnd2 import TkinterDnD


@pytest.fixture(scope="session")
def native_tk_root():
    # TkDnD loads a native extension; do not unload/reinitialize Tcl between
    # test classes. Exercise the same single-root lifecycle as the real app.
    root = TkinterDnD.Tk()
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture(scope="class")
def tk_root(request, native_tk_root):
    request.cls.root = native_tk_root
