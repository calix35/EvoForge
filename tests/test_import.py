import evoforge


def test_package_imports() -> None:
    assert evoforge.__version__ == "0.2.0"


def test_core_and_plugin_registration_keep_optional_libraries_unloaded():
    import subprocess
    import sys

    script = """
import builtins, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'pymoo', 'numpy', 'sklearn', 'aquacrop'}:
        raise AssertionError(name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from evoforge.core import Experiment
from evoforge.cli.main import _default_plugin_registry
registry = _default_plugin_registry()
assert 'pymoo.nsga2' in registry
assert 'example.zdt1' in registry
assert not {'pymoo', 'numpy', 'sklearn', 'aquacrop'} & sys.modules.keys()
"""
    subprocess.run([sys.executable, "-c", script], check=True)
