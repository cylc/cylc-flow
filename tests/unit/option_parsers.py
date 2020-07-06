import optparse

import pytest

from cylc.flow.option_parsers import Options


@pytest.fixture
def simple_parser():
    """Simple option parser."""
    parser = optparse.OptionParser()
    parser.add_option('-a', action='store')
    parser.add_option('-b', action='store_true')
    parser.add_option('-c', default='C')
    return parser


def test_options(simple_parser):
    """It is a substitute for an optparse options object."""
    options = Options(parser=simple_parser)
    opts = options(a=1, b=True)

    # we can access options as attributes
    assert opts.a == 1
    assert opts.b is True

    # defaults are automatically substituted
    assert opts.c == 'C'

    # get-like syntax should work
    assert opts.get('d', 42) == 42

    # invalid keys result in KeyErrors
    with pytest.raises(KeyError):
        opts.d
    with pytest.raises(KeyError):
        opts(d=1)

    # just for fun we can still use dict syntax
    assert opts['a'] == 1
