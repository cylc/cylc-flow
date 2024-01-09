# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from contextlib import redirect_stdout
import io
import sys
from types import SimpleNamespace
from typing import List

import pytest
from pytest import param

import cylc.flow.flags
from cylc.flow.option_parsers import (
    CylcOptionParser as COP, Options, combine_options, combine_options_pair,
    OptionSettings, cleanup_sysargv, filter_sysargv
)


USAGE_WITH_COMMENT = "usage \n # comment"
ARGS = 'args'
KWARGS = 'kwargs'
SOURCES = 'sources'
USEIF = 'useif'


@pytest.fixture(scope='module')
def parser():
    return COP(
        USAGE_WITH_COMMENT,
        argdoc=[('SOME_ARG', "Description of SOME_ARG")]
    )


@pytest.mark.parametrize(
    'args,verbosity',
    [
        ([], 0),
        (['-v'], 1),
        (['-v', '-v', '-v'], 3),
        (['-q'], -1),
        (['-q', '-q', '-q'], -3),
        (['-q', '-v', '-q'], -1),
        (['--debug'], 2),
        (['--debug', '-q'], 1),
        (['--debug', '-v'], 3),
    ]
)
def test_verbosity(
    args: List[str],
    verbosity: int,
    parser: COP, monkeypatch: pytest.MonkeyPatch
) -> None:
    """-v, -q, --debug should be additive."""
    # patch the cylc.flow.flags value so that it gets reset after the test
    monkeypatch.setattr('cylc.flow.flags.verbosity', None)
    opts, args = parser.parse_args(['default-arg'] + args)
    assert opts.verbosity == verbosity
    # test side-effect, the verbosity flag should be set
    assert cylc.flow.flags.verbosity == verbosity


def test_help_color(monkeypatch: pytest.MonkeyPatch, parser: COP):
    """Test for colorized comments in 'cylc cmd --help --color=always'."""
    # This colorization is done on the fly when help is printed.
    monkeypatch.setattr("sys.argv", ['cmd', 'foo', '--color=always'])
    parser.parse_args(None)
    assert parser.values.color == "always"
    f = io.StringIO()
    with redirect_stdout(f):
        parser.print_help()
    assert not (f.getvalue()).startswith("Usage: " + USAGE_WITH_COMMENT)


def test_help_nocolor(monkeypatch: pytest.MonkeyPatch, parser: COP):
    """Test for no colorization in 'cylc cmd --help --color=never'."""
    # This colorization is done on the fly when help is printed.
    monkeypatch.setattr(sys, "argv", ['cmd', 'foo', '--color=never'])
    parser.parse_args(None)
    assert parser.values.color == "never"
    f = io.StringIO()
    with redirect_stdout(f):
        parser.print_help()
    assert (f.getvalue()).startswith("Usage: " + USAGE_WITH_COMMENT)


def test_Options_std_opts():
    """Test Python Options API with standard options."""
    parser = COP(USAGE_WITH_COMMENT, auto_add=True)
    MyOptions = Options(parser)
    MyValues = MyOptions(verbosity=1)
    assert MyValues.verbosity == 1


# Add overlapping args tomorrow
@pytest.mark.parametrize(
    'first, second, expect',
    [
        param(
            [{ARGS: ['-f', '--foo'], KWARGS: {}, SOURCES: {'do'}}],
            [{ARGS: ['-f', '--foo'], KWARGS: {}, SOURCES: {'dont'}}],
            (
                [{
                    ARGS: ['-f', '--foo'], KWARGS: {},
                    SOURCES: {'do', 'dont'}, USEIF: ''
                }]
            ),
            id='identical arg lists unchanged'
        ),
        param(
            [{ARGS: ['-f', '--foo'], KWARGS: {}, SOURCES: {'fall'}}],
            [{
                ARGS: ['-f', '--foolish'],
                KWARGS: {'help': 'not identical'},
                SOURCES: {'fold'}}],
            (
                [
                    {
                        ARGS: ['--foo'], KWARGS: {}, SOURCES: {'fall'},
                        USEIF: ''
                    },
                    {
                        ARGS: ['--foolish'],
                        KWARGS: {'help': 'not identical'},
                        SOURCES: {'fold'},
                        USEIF: ''
                    }
                ]
            ),
            id='different arg lists lose shared names'
        ),
        param(
            [{ARGS: ['-f', '--foo'], KWARGS: {}, SOURCES: {'cook'}}],
            [{
                ARGS: ['-f', '--foo'],
                KWARGS: {'help': 'not identical', 'dest': 'foobius'},
                SOURCES: {'bake'},
                USEIF: ''
            }],
            None,
            id='different args identical arg list cause exception'
        ),
        param(
            [{ARGS: ['-g', '--goo'], KWARGS: {}, SOURCES: {'knit'}}],
            [{ARGS: ['-f', '--foo'], KWARGS: {}, SOURCES: {'feed'}}],
            [
                {
                    ARGS: ['-g', '--goo'], KWARGS: {},
                    SOURCES: {'knit'}, USEIF: ''
                },
                {
                    ARGS: ['-f', '--foo'], KWARGS: {},
                    SOURCES: {'feed'}, USEIF: ''
                },
            ],
            id='all unrelated args added'
        ),
        param(
            [
                {ARGS: ['-f', '--foo'], KWARGS: {}, SOURCES: {'work'}},
                {ARGS: ['-r', '--redesdale'], KWARGS: {}, SOURCES: {'work'}}
            ],
            [
                {ARGS: ['-f', '--foo'], KWARGS: {}, SOURCES: {'sink'}},
                {
                    ARGS: ['-b', '--buttered-peas'],
                    KWARGS: {}, SOURCES: {'sink'}
                }
            ],
            [
                {
                    ARGS: ['-f', '--foo'],
                    KWARGS: {},
                    SOURCES: {'work', 'sink'},
                    USEIF: ''
                },
                {
                    ARGS: ['-b', '--buttered-peas'],
                    KWARGS: {},
                    SOURCES: {'sink'},
                    USEIF: ''
                },
                {
                    ARGS: ['-r', '--redesdale'],
                    KWARGS: {},
                    SOURCES: {'work'},
                    USEIF: ''
                },
            ],
            id='do not repeat args'
        ),
        param(
            [
                {
                    ARGS: ['-f', '--foo'],
                    KWARGS: {},
                    SOURCES: {'push'}
                },
            ],
            [],
            [
                {
                    ARGS: ['-f', '--foo'],
                    KWARGS: {},
                    SOURCES: {'push'},
                    USEIF: ''
                },
            ],
            id='one empty list is fine'
        )
    ]
)
def test_combine_options_pair(first, second, expect):
    """It combines sets of options"""
    first = [
        OptionSettings(i[ARGS], sources=i[SOURCES], **i[KWARGS])
        for i in first
    ]
    second = [
        OptionSettings(i[ARGS], sources=i[SOURCES], **i[KWARGS])
        for i in second
    ]
    if expect is not None:
        result = combine_options_pair(first, second)
        assert [i.__dict__ for i in result] == expect
    else:
        with pytest.raises(Exception, match='Clashing Options'):
            combine_options_pair(first, second)


@pytest.mark.parametrize(
    'inputs, expect',
    [
        param(
            [
                ([OptionSettings(
                    ['-i', '--inflammable'], help='', sources={'wish'}
                )]),
                ([OptionSettings(
                    ['-f', '--flammable'], help='', sources={'rest'}
                )]),
                ([OptionSettings(
                    ['-n', '--non-flammable'], help='', sources={'swim'}
                )]),
            ],
            [
                {ARGS: ['-i', '--inflammable']},
                {ARGS: ['-f', '--flammable']},
                {ARGS: ['-n', '--non-flammable']}
            ],
            id='merge three argsets no overlap'
        ),
        param(
            [
                [
                    OptionSettings(
                        ['-m', '--morpeth'], help='', sources={'stop'}),
                    OptionSettings(
                        ['-r', '--redesdale'], help='', sources={'stop'}),
                ],
                [
                    OptionSettings(
                        ['-b', '--byker'], help='', sources={'walk'}),
                    OptionSettings(
                        ['-r', '--roxborough'], help='', sources={'walk'}),
                ],
                [
                    OptionSettings(
                        ['-b', '--bellingham'], help='', sources={'leap'}),
                ]
            ],
            [
                {ARGS: ['--bellingham']},
                {ARGS: ['--roxborough']},
                {ARGS: ['--redesdale']},
                {ARGS: ['--byker']},
                {ARGS: ['-m', '--morpeth']}
            ],
            id='merge three overlapping argsets'
        ),
        param(
            [
                ([]),
                (
                    [
                        OptionSettings(
                            ['-c', '--campden'], help='x', sources={'foo'})
                    ]
                )
            ],
            [
                {ARGS: ['-c', '--campden']}
            ],
            id="empty list doesn't clear result"
        ),
    ]
)
def test_combine_options(inputs, expect):
    """It combines multiple input sets"""
    result = combine_options(*inputs)
    result_args = [i.args for i in result]

    # Order of args irrelevent to test
    for option in expect:
        assert option[ARGS] in result_args


@pytest.mark.parametrize(
    'argv_before, kwargs, expect',
    [
        param(
            'vip myworkflow -f something -b something_else --baz'.split(),
            {
                'script_name': 'play',
                'workflow_id': 'myworkflow',
                'compound_script_opts': [
                    OptionSettings(['--foo', '-f']),
                    OptionSettings(['--bar', '-b'], action='store'),
                    OptionSettings(['--baz'], action='store_true'),
                ],
                'script_opts': [
                    OptionSettings(['--foo', '-f']),
                ]
            },
            'play myworkflow -f something'.split(),
            id='remove some opts'
        ),
        param(
            'vip myworkflow'.split(),
            {
                'script_name': 'play',
                'workflow_id': 'myworkflow',
                'compound_script_opts': [
                    OptionSettings(['--foo', '-f']),
                    OptionSettings(['--bar', '-b']),
                    OptionSettings(['--baz']),
                ],
                'script_opts': []
            },
            'play myworkflow'.split(),
            id='no opts to keep'
        ),
        param(
            'vip ./myworkflow --foo something'.split(),
            {
                'script_name': 'play',
                'workflow_id': 'myworkflow',
                'compound_script_opts': [
                    OptionSettings(['--foo', '-f'])],
                'script_opts': [
                    OptionSettings(['--foo', '-f']),
                ],
                'source': './myworkflow',
            },
            'play --foo something myworkflow'.split(),
            id='replace path'
        ),
        param(
            'vip --foo something'.split(),
            {
                'script_name': 'play',
                'workflow_id': 'myworkflow',
                'compound_script_opts': [
                    OptionSettings(['--foo', '-f'])],
                'script_opts': [
                    OptionSettings(['--foo', '-f']),
                ],
                'source': './myworkflow',
            },
            'play --foo something myworkflow'.split(),
            id='no path given'
        ),
    ]
)
def test_cleanup_sysargv(monkeypatch, argv_before, kwargs, expect):
    """It replaces the contents of sysargv with Cylc Play argv items.
    """
    # Fake up sys.argv: for this test.
    dummy_cylc_path = ['/pathto/my/cylc/bin/cylc']
    monkeypatch.setattr(sys, 'argv', dummy_cylc_path + argv_before)
    # Fake options too:
    opts = SimpleNamespace(**{
        i.args[0].replace('--', ''): i for i in kwargs['compound_script_opts']
    })

    kwargs.update({'options': opts})
    if not kwargs.get('source', None):
        kwargs.update({'source': ''})

    # Test the script:
    cleanup_sysargv(**kwargs)
    assert sys.argv == dummy_cylc_path + expect


@pytest.mark.parametrize(
    'sysargs, simple, compound, expect', (
        param(
            # Test for https://github.com/cylc/cylc-flow/issues/5905
            '--no-run-name --workflow-name=name'.split(),
            ['--no-run-name'],
            ['--workflow-name'],
            [],
            id='--workflow-name=name'
        ),
        param(
            '--foo something'.split(),
            [], [], '--foo something'.split(),
            id='no-opts-removed'
        ),
        param(
            [], ['--foo'], ['--bar'], [],
            id='Null-check'
        ),
        param(
            '''--keep1 --keep2 42 --keep3=Hi
            --throw1 --throw2 84 --throw3=There
            '''.split(),
            ['--throw1'],
            '--throw2 --throw3'.split(),
            '--keep1 --keep2 42 --keep3=Hi'.split(),
            id='complex'
        ),
        param(
            "--foo 'foo=42' --bar='foo=94'".split(),
            [], ['--foo'],
            ['--bar=\'foo=94\''],
            id='--bar=\'foo=94\''
        )
    )
)
def test_filter_sysargv(
    sysargs, simple, compound, expect
):
    """It returns the subset of sys.argv that we ask for.

    n.b. The three most basic cases for this function are stored in
    its own docstring.
    """
    assert filter_sysargv(sysargs, simple, compound) == expect


class TestOptionSettings():
    @staticmethod
    def test_init():
        args = ['--foo', '-f']
        kwargs = {'bar': 42}
        sources = {'touch'}
        useif = 'hello'

        result = OptionSettings(
            args, sources=sources, useif=useif, **kwargs)

        assert result.__dict__ == {
            'kwargs': kwargs, 'sources': sources,
            'useif': useif, 'args': args
        }

    @staticmethod
    @pytest.mark.parametrize(
        'first, second, expect',
        (
            param(
                (['--foo', '-f'], {'bar': 42}, {'touch'}, 'hello'),
                (['--foo', '-f'], {'bar': 42}, {'touch'}, 'hello'),
                True, id='Totally the same'),
            param(
                (['--foo', '-f'], {'bar': 42}, {'touch'}, 'hello'),
                (['--foo', '-f'], {'bar': 42}, {'wibble'}, 'byee'),
                True, id='Differing extras'),
            param(
                (['-f'], {'bar': 42}, {'touch'}, 'hello'),
                (['--foo', '-f'], {'bar': 42}, {'wibble'}, 'byee'),
                False, id='Not equal args'),
        )
    )
    def test___eq__args_intersection(first, second, expect):
        args, kwargs, sources, useif = first
        first = OptionSettings(
            args, sources=sources, useif=useif, **kwargs)
        args, kwargs, sources, useif = second
        second = OptionSettings(
            args, sources=sources, useif=useif, **kwargs)
        assert (first == second) == expect

    @staticmethod
    @pytest.mark.parametrize(
        'first, second, expect',
        (
            param(
                ['--foo', '-f'],
                ['--foo', '-f'],
                ['--foo', '-f'],
                id='Totally the same'),
            param(
                ['--foo', '-f'],
                ['--foolish', '-f'],
                ['-f'],
                id='Some overlap'),
            param(
                ['--foo', '-f'],
                ['--bar', '-b'],
                [],
                id='No overlap'),
        )
    )
    def test___and__(first, second, expect):
        first = OptionSettings(first)
        second = OptionSettings(second)
        assert sorted(first & second) == sorted(expect)

    @staticmethod
    @pytest.mark.parametrize(
        'first, second, expect',
        (
            param(
                ['--foo', '-f'],
                ['--foo', '-f'],
                [],
                id='Totally the same'),
            param(
                ['--foo', '-f'],
                ['--foolish', '-f'],
                ['--foo'],
                id='Some overlap'),
            param(
                ['--foolish', '-f'],
                ['--foo', '-f'],
                ['--foolish'],
                id='Some overlap not commuting'),
            param(
                ['--foo', '-f'],
                ['--bar', '-b'],
                ['--foo', '-f'],
                id='No overlap'),
        )
    )
    def test___sub__args_subtraction(first, second, expect):
        first = OptionSettings(first)
        second = OptionSettings(second)
        assert sorted(first - second) == sorted(expect)

    @staticmethod
    def test__in_list():
        """It is in a list."""
        first = OptionSettings(['--foo'])
        second = OptionSettings(['--foo'])
        third = OptionSettings(['--bar'])
        assert first._in_list([second, third]) is True
