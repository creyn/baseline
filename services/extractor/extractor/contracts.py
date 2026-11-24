"""Access to the shared contracts in the repository's contracts/ folder.

The folder is found next to the repository root, or through CONTRACTS_DIR (the
container image copies it there). One implementation of the text blob checks is
shared by the extractor and the contract tests.
"""
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
CONTRACTS_DIR = os.environ.get('CONTRACTS_DIR') or os.path.normpath(os.path.join(_HERE, '..', '..', '..', 'contracts'))


def _load_module(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(CONTRACTS_DIR, f'{name}.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


text_checks = _load_module('text_checks')


def schema(name):
    """A schema by file stem, e.g. 'text.v1'."""
    with open(os.path.join(CONTRACTS_DIR, f'{name}.schema.json'), encoding='utf-8') as f:
        return json.load(f)
