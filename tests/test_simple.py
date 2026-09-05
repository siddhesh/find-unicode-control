import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(ROOT, 'tests', 'examples')

BIDI = u'/* ‮ comment */\n'


def run(*args):
    env = dict(os.environ)
    env['PYTHONPATH'] = os.path.join(ROOT, 'src')
    proc = subprocess.Popen([sys.executable, '-m', 'find_unicode_control'] +
                            list(args), cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc.communicate()
    return proc.returncode


def write(path, text):
    with open(str(path), 'wb') as f:
        f.write(text.encode('utf-8'))


def test_simple():
    assert run('-p', 'bidi', EXAMPLES) == 0


def test_findings(tmpdir):
    source = tmpdir.join('trojan.c')
    write(source, BIDI)
    assert run('-p', 'bidi', str(source)) == 1


def test_notests(tmpdir):
    # -t used to fail with UnboundLocalError before the scan lists were
    # declared global.
    testdir = tmpdir.mkdir('testdir')
    write(testdir.join('trojan.c'), BIDI)
    assert run('-p', 'bidi', str(tmpdir)) == 1
    assert run('-p', 'bidi', '-t', str(tmpdir)) == 0


def test_config(tmpdir):
    # -c used to fail with AttributeError on importlib.util.
    source = tmpdir.join('trojan.c')
    write(source, BIDI)
    config = tmpdir.join('settings.py')
    write(config, "scan_exclude = [r'trojan\\.c$']\n")
    assert run('-p', 'bidi', str(source)) == 1
    assert run('-p', 'bidi', '-c', str(config), str(source)) == 0
