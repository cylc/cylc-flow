from contextlib import contextmanager
from difflib import unified_diff
import os
from pathlib import Path
import re
from time import sleep
from secrets import token_hex

import pytest
from urwid.display import html_fragment

from cylc.flow.id import Tokens
from cylc.flow.tui.app import TuiApp
from cylc.flow.tui.overlay import _get_display_id


SCREENSHOT_DIR = Path(__file__).parent / 'screenshots'


def configure_screenshot(v_term_size):
    """Configure Urwid HTML screenshots."""
    screen = html_fragment.HtmlGenerator()
    screen.set_terminal_properties(256)
    screen.register_palette(TuiApp.palette)
    html_fragment.screenshot_init(
        [tuple(map(int, v_term_size.split(',')))],
        []
    )
    return screen, html_fragment


def format_test_failure(expected, got, description):
    """Return HTML to represent a screenshot test failure.

    Args:
        expected:
            HTML fragment for the expected screenshot.
        got:
            HTML fragment for the test screenshot.
        description:
            Test description.

    """
    diff = '\n'.join(unified_diff(
        expected.splitlines(),
        got.splitlines(),
        fromfile='expected',
        tofile='got',
    ))
    return f'''
        <html>
            <head></head>
            <h2>{description}</h2>
            <table>
                <tr>
                    <td><b>Expected</b></td>
                    <td><b>Got</b></td>
                </tr>
                <tr>
                    <td>{expected}</td>
                    <td>{got}</td>
                </tr>
            </table>
            <br />
            <h4>Diff:</h4>
            <pre>{ diff }</pre>
        </html>
    '''


class RakiuraSession:
    """Convenience class for accessing Rakiura functionality."""

    def __init__(self, app, html_fragment, test_dir, test_name):
        self.app = app
        self.html_fragment = html_fragment
        self.test_dir = test_dir
        self.test_name = test_name

    def user_input(self, *keys):
        """Simulate a user pressing keys.

        Each "key" is a keyboard button e.g. "x" or "enter".

        If you provide more than one key, each one will be pressed, one
        after another.

        You can combine keys in a single string, e.g. "ctrl d".
        """
        return self.app.loop.process_input(keys)

    def compare_screenshot(
        self,
        name,
        description,
        retries=3,
        delay=0.1,
        force_update=True,
    ):
        """Take a screenshot and compare it to one taken previously.

        To update the screenshot, set the environment variable
        "CYLC_UPDATE_SCREENSHOTS" to "true".

        Note, if the comparison fails, "force_update" is called and the
        test is retried.

        Arguments:
            name:
                The name to use for the screenshot, this is used in the
                filename for the generated HTML fragment.
            description:
                A description of the test to be used on test failure.
            retries:
                The maximum number of retries for this test before failing.
            delay:
                The delay between retries. This helps overcome timing issues
                with data provision.

        Raises:
            Exception:
                If the screenshot does not match the reference.

        """
        filename = SCREENSHOT_DIR / f'{self.test_name}.{name}.html'

        exc = None
        for _try in range(retries):
            # load the expected result
            expected = '<screenshot not found>'
            if filename.exists():
                with open(filename, 'r') as expected_file:
                    expected = expected_file.read()
            # update to pick up latest data
            if force_update:
                self.force_update()
            # force urwid to draw the screen
            # (the main loop isn't runing so this doesn't happen automatically)
            self.app.loop.draw_screen()
            # take a screenshot
            screenshot = self.html_fragment.screenshot_collect()[-1]

            try:
                if expected != screenshot:
                    # screenshot does not match
                    # => write an html file with the visual diff
                    out = self.test_dir / filename.name
                    with open(out, 'w+') as out_file:
                        out_file.write(
                            format_test_failure(
                                expected,
                                screenshot,
                                description,
                            )
                        )
                    raise Exception(
                        'Screenshot differs:'
                        '\n* Set "CYLC_UPDATE_SCREENSHOTS=true" to update'
                        f'\n* To debug see: file:////{out}'
                    )

                break
            except Exception as exc_:
                exc = exc_
                # wait a while to allow the updater to do its job
                sleep(delay)
        else:
            if os.environ.get('CYLC_UPDATE_SCREENSHOTS', '').lower() == 'true':
                with open(filename, 'w+') as expected_file:
                    expected_file.write(screenshot)
            else:
                raise exc

    def force_update(self):
        """Run Tui's update method.

        This is done automatically by compare_screenshot but you may want to
        call it in a test, e.g. before pressing navigation keys.

        With Rakiura, the Tui event loop is not running so the data is never
        refreshed.

        You do NOT need to call this method for key presses, but you do need to
        call this if the data has changed (e.g. if you've changed a task state)
        OR if you've changed any filters (because filters are handled by the
        update code).
        """
        # flush any prior updates
        self.app.get_update()
        # wait for the next update
        while not self.app.update():
            pass

    def wait_until_loaded(self, *ids, retries=20):
        """Wait until the given ID appears in the Tui tree, then expand them.

        Useful for waiting whilst Tui loads a workflow.

        Note, this is a blocking wait with no timeout!
        """
        exc = None
        try:
            ids = self.app.wait_until_loaded(*ids, retries=retries)
        except Exception as _exc:
            exc = _exc
        if ids:
            msg = (
                'Requested nodes did not appear in Tui after'
                f' {retries} retries: '
                + ', '.join(ids)
            )
            if exc:
                msg += f'\n{exc}'
            self.compare_screenshot(f'fail-{token_hex(4)}', msg, 1)


@pytest.fixture
def rakiura(test_dir, request, monkeypatch):
    """Visual regression test framework for Urwid apps.

    Like Cypress but for Tui so named after a NZ island with lots of Tuis.

    When called this yields a RakiuraSession object loaded with test
    utilities. All tests have default retries to avoid flaky tests.

    Similar to the "start" fixture, which starts a Scheduler without running
    the main loop, rakiura starts Tui without running the main loop.

    Arguments:
        workflow_id:
            The "WORKFLOW" argument of the "cylc tui" command line.
        size:
            The virtual terminal size for screenshots as a comma
            separated string e.g. "80,50" for 80 cols wide by 50 rows tall.

    Returns:
        A RakiuraSession context manager which provides useful utilities for
        testing.

    """
    return _rakiura(test_dir, request, monkeypatch)


@pytest.fixture
def mod_rakiura(test_dir, request, monkeypatch):
    """Same as rakiura but configured to view module-scoped workflows.

    Note: This is *not* a module-scoped fixture (no need, creating Tui sessions
    is not especially slow), it is configured to display module-scoped
    "scheduler" fixtures (which may be more expensive to create/destroy).
    """
    return _rakiura(test_dir.parent, request, monkeypatch)


def _rakiura(test_dir, request, monkeypatch):
    # make the workflow and scan update intervals match (more reliable)
    # and speed things up a little whilst we're at it
    monkeypatch.setattr(
        'cylc.flow.tui.updater.Updater.BASE_UPDATE_INTERVAL',
        0.1,
    )
    monkeypatch.setattr(
        'cylc.flow.tui.updater.Updater.BASE_SCAN_INTERVAL',
        0.1,
    )

    # the user name and the prefix of workflow IDs are both variable
    # so we patch the render functions to make test output stable
    def get_display_id(id_):
        tokens = Tokens(id_)
        return _get_display_id(
            tokens.duplicate(
                user='cylc',
                workflow=tokens.get('workflow', '').rsplit('/', 1)[-1],
            ).id
        )
    monkeypatch.setattr('cylc.flow.tui.util.ME', 'cylc')
    monkeypatch.setattr(
        'cylc.flow.tui.util._display_workflow_id',
        lambda data: data['name'].rsplit('/', 1)[-1]
    )
    monkeypatch.setattr(
        'cylc.flow.tui.overlay._get_display_id',
        get_display_id,
    )

    # standardise environment for tests
    monkeypatch.setenv('EDITOR', 'nvim')
    monkeypatch.setenv('GEDITOR', 'gvim -f')
    monkeypatch.setenv('PAGER', 'less')

    # filter Tui so that only workflows created within our test show up
    id_base = str(test_dir.relative_to(Path("~/cylc-run").expanduser()))
    workflow_filter = re.escape(id_base) + r'/.*'

    @contextmanager
    def _rakiura(workflow_id=None, size='80,50'):
        screen, html_fragment = configure_screenshot(size)
        app = TuiApp(screen=screen)
        with app.main(
            workflow_id,
            id_filter=workflow_filter,
            interactive=False,
        ):
            yield RakiuraSession(
                app,
                html_fragment,
                test_dir,
                request.function.__name__,
            )

    return _rakiura
