import asyncio
import signal
from subprocess import (
    PIPE,
    Popen,
)
import sys
from time import sleep

from cylc.flow.remote import watch_and_kill
from cylc.flow.scripts.cylc import pycoverage


if __name__ == '__main__':

    # Ignore SIGHUP (death of controlling process) for all processes, as
    # this might give a false positive test result:
    signal.signal(signal.SIGHUP, lambda *_: None)

    def log_start(proc_type: str):
        print(f'start {proc_type}')

    def log_term(proc_type: str):
        print(f'term  {proc_type}')
        sys.exit(1)

    def log_exit(proc_type: str):
        print(f'exit  {proc_type}')

    def parent() -> None:
        log_start('parent')
        signal.signal(signal.SIGTERM, lambda *_: log_term('parent'))
        child = Popen([sys.executable, __file__, 'child'])
        asyncio.run(watch_and_kill(child, interval=0.1))
        child.wait()
        log_exit('parent')

    def child() -> None:
        log_start('child')
        signal.signal(signal.SIGTERM, lambda *_: log_term('child'))
        sleep(60)
        log_exit('child')

    def launcher() -> None:
        log_start('launcher')
        signal.signal(signal.SIGTERM, lambda *_: log_term('launcher'))
        Popen([sys.executable, __file__, 'parent']).wait()
        log_exit('launcher')

    with pycoverage(sys.argv):
        if 'parent' in sys.argv:
            parent()
        elif 'child' in sys.argv:
            child()
        elif 'launcher' in sys.argv:
            launcher()
        else:
            raise ValueError('Unknown or missing type argument')

    sys.exit(0)


def test_watch_and_kill():
    """It should detect changes in the process tree.

    When this test runs, we get the following process tree:
    pytest
    `-- launcher
        `-- parent
             `-- child

    The test then kills the launcher process, changing the process tree.
    The parent running watch_and_kill() should detect this when monitoring the
    child's process tree and terminate the child.
    """
    launcher = Popen(
        [sys.executable, __file__, 'launcher'], stdout=PIPE, text=True
    )
    sleep(5)
    launcher.terminate()
    out, err = launcher.communicate(timeout=10)
    print(out)  # for debugging
    print(err, file=sys.stderr)
    assert out.splitlines() == [
        # all three processes start
        'start launcher',
        'start parent',
        'start child',

        # the launcher is terminated
        'term  launcher',

        # the parent detects its pid changing and terminates the child
        'term  child',

        # the parent exits cleanly
        'exit  parent',
    ]
