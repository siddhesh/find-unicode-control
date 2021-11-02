from subprocess import check_output
import pytest

def test_simple():
    check_output('python find_unicode_control.py *', shell=True)
