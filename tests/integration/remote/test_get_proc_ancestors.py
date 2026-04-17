import signal
from subprocess import (
    PIPE,
    Popen,
)
import sys
from time import sleep

from cylc.flow.remote import get_proc_ancestors
from cylc.flow.scripts.cylc import pycoverage

"""Test get_proc_ancestors() detects changes in the process tree."""


PROC_TREE_CHANGED = "Proc tree changed:"


if __name__ == '__main__':

    def child() -> None:
        print(gpa := get_proc_ancestors())
        while get_proc_ancestors() == gpa:
            sleep(0.1)
        print(PROC_TREE_CHANGED, get_proc_ancestors())

    def parent() -> None:
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(1))
        Popen([sys.executable, __file__, 'child']).wait()

    with pycoverage(sys.argv):
        if 'child' in sys.argv:
            child()
        elif 'parent' in sys.argv:
            parent()
        else:
            raise ValueError('Unknown or missing type argument')

    sys.exit(0)


def test_get_proc_ancestors():
    parent = Popen(
        [sys.executable, __file__, 'parent'], stdout=PIPE, text=True
    )
    sleep(5)
    parent.terminate()
    out, err = parent.communicate(timeout=5)
    print(out)  # for debugging
    print(err, file=sys.stderr)
    assert PROC_TREE_CHANGED in out
