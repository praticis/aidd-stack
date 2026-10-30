"""The case table's star imports, as `test_python_types.py` runs every case: the modules a star import of a case names,
and the cases. A star import binds its module's `__all__`, or its public names, and a later binding holds a name."""

A_RUN, B_RUN, BASE_RUN = "app/models:A.run", "app/models:B.run", "app/models:Base.run"

STAR_MODULES = {
    "app/again.py": "from app.everything import *\n",
    "app/listed.py": "from app.models import A\nclass B:\n    def run(self): pass\n__all__ = ['A']\n",
    "app/hidden.py": "from app.models import A as _B\n",
    "app/pkg/__init__.py": "__all__ = ['inner']\n",
    "app/pkg/inner.py": "class C:\n    def run(self): pass\n",
    "app/computed.py": "from app.models import *\n__all__ = [n for n in dir() if not n.startswith('_')]\n",
}
STAR_CASES = {
    "a-base-a-star-import-binds": (
        "from app.models import *\nclass C(Base):\n    pass\ndef main(): return C().run()\n", BASE_RUN, "typed"),
    "a-name-a-star-import-of-a-star-import-binds": (
        "from app.again import *\ndef main(): return B().run()\n", B_RUN, "typed"),
    "a-name-out-of-the-modules-all": (
        "from app.models import B\nfrom app.listed import *\ndef main(): return B().run()\n", B_RUN, "typed",
        "app/listed:B.run"),
    "a-private-name-of-a-module-with-no-all": (
        "from app.models import B as _B\nfrom app.hidden import *\ndef main(): return _B().run()\n", B_RUN, "typed",
        A_RUN),
    "a-name-a-later-star-import-binds-again": (
        "from app.models import A as B\nfrom app.everything import *\ndef main(): return B().run()\n", B_RUN, "typed",
        A_RUN),
    "a-name-the-module-binds-after-a-star-import": (
        "from app.everything import *\nfrom app.models import A as B\ndef main(): return B().run()\n", A_RUN, "typed",
        B_RUN),
    "a-submodule-a-packages-all-names": (
        "from app.pkg import *\ndef main(): return inner.C().run()\n", "app/pkg/inner:C.run", "typed"),
}
