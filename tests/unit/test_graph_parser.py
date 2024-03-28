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
"""Unit tests for the GraphParser."""

import logging
from typing import Dict, List
import pytest
from itertools import product
from pytest import param
from types import SimpleNamespace

from cylc.flow import CYLC_LOG
from cylc.flow.exceptions import GraphParseError, ParamExpandError
from cylc.flow.graph_parser import GraphParser
from cylc.flow.task_outputs import (
    TASK_OUTPUT_SUBMITTED,
    TASK_OUTPUT_SUBMIT_FAILED,
    TASK_OUTPUT_STARTED,
    TASK_OUTPUT_SUCCEEDED,
    TASK_OUTPUT_FAILED
)


@pytest.mark.parametrize(
    'graph',
    [
        't1 => & t2',
        't1 => t2 &',
        '& t1 => t2',
        't1 & => t2',
        't1 => => t2'
    ]
)
def test_parse_graph_fails_null_task_name(graph):
    """Test fail null task names."""
    with pytest.raises(GraphParseError) as cm:
        GraphParser().parse_graph(graph)
        assert "Null task name in graph:" in str(cm.value)


@pytest.mark.parametrize('seq', ('&', '|', '=>'))
@pytest.mark.parametrize(
    'graph, expected_err',
    [
        [
            "{0} b",
            "Leading {0}"
        ],
        [
            "a {0}",
            "Dangling {0}"
        ],
        [
            "{0} b {0} c",
            "Leading {0}"
        ],
        [
            "a {0} b {0}",
            "Dangling {0}"
        ]
    ]
)
def test_graph_syntax_errors_2(seq, graph, expected_err):
    """Test various graph syntax errors."""
    graph = graph.format(seq)
    expected_err = expected_err.format(seq)
    with pytest.raises(GraphParseError) as cm:
        GraphParser().parse_graph(graph)
    assert (
        expected_err in str(cm.value)
    )


@pytest.mark.parametrize(
    'graph, expected_err',
    [
        (
            "a b => c",
            "Bad graph node format"
        ),
        (
            "a => b c",
            "Bad graph node format"
        ),
        (
            "!foo => bar",
            "Suicide markers must be on the right of a trigger:"
        ),
        (
            "( foo & bar => baz",
            'Mismatched parentheses in: "(foo&bar"'
        ),
        (
            "a => b & c)",
            'Mismatched parentheses in: "b&c)"'
        ),
        (
            "(a => b & c)",
            'Mismatched parentheses in: "(a"'
        ),
        (
            "(a => b[+P1]",
            'Mismatched parentheses in: "(a"'
        ),
        (
            """(a | b & c) => d
               foo => bar
               (a | b & c) => !d""",
            "can't trigger both d and !d"
        ),
        (
            "a => b | c",
            "Illegal OR on right side"
        ),
        (
            "foo && bar => baz",
            "The graph AND operator is '&'"
        ),
        (
            "foo || bar => baz",
            "The graph OR operator is '|'"
        ),
        param(
            # See https://github.com/cylc/cylc-flow/issues/5844
            "foo => bar[1649]",
            'Invalid cycle point offsets only on right',
            id='no-cycle-point-RHS'
        ),
    ]
)
def test_graph_syntax_errors(graph, expected_err):
    """Test various graph syntax errors."""
    with pytest.raises(GraphParseError) as cm:
        GraphParser().parse_graph(graph)
    assert expected_err in str(cm.value)


def test_parse_graph_simple():
    """Test parsing graphs."""
    # added white spaces and comments to show that these change nothing

    gp = GraphParser()
    gp.parse_graph('a => b\n  \n# this is a comment\n')

    original = gp.original
    triggers = gp.triggers
    families = gp.family_map

    assert (
        original == {'a': {'': ''}, 'b': {'a:succeeded': 'a:succeeded'}}
    )

    assert (
        triggers == {
            'a': {'': ([], False)},
            'b': {'a:succeeded': (['a:succeeded'], False)}
        }
    )
    assert not families


@pytest.mark.parametrize(
    'graph, expect',
    [
        param(
            'a => b\n=> c',
            SimpleNamespace(
                original={
                    'c': {'b:succeeded': 'b:succeeded'},
                    'b': {'a:succeeded': 'a:succeeded'},
                    'a': {'': ''}
                },
                triggers={
                    'c': {'b:succeeded': (['b:succeeded'], False)},
                    'b': {'a:succeeded': (['a:succeeded'], False)},
                    'a': {'': ([], False)}
                },
                families={}
            ),
            id='line break on =>'
        ),
        param(
            'a & b\n& c',
            SimpleNamespace(
                original={'b': {'': ''}, 'a': {'': ''}, 'c': {'': ''}},
                triggers={
                    'b': {'': ([], False)},
                    'a': {'': ([], False)},
                    'c': {'': ([], False)}
                },
                families={}
            ),
            id='line break on &'
        ),
        param(
            'a | b\n| c',
            SimpleNamespace(
                original={'b': {'': ''}, 'c': {'': ''}, 'a': {'': ''}},
                triggers={
                    'b': {'': ([], False)},
                    'c': {'': ([], False)},
                    'a': {'': ([], False)}
                },
                families={}
            ),
            id='line break on |'
        )
    ]
)
def test_parse_graph_simple_with_break_line_01(graph, expect):
    """Test parsing graphs."""
    parser = GraphParser()
    parser.parse_graph(graph)
    assert parser.original == expect.original
    assert parser.triggers == expect.triggers
    assert not parser.family_map


def test_parse_graph_simple_with_break_line_02():
    """Test parsing graphs."""
    gp = GraphParser()
    gp.parse_graph(
        'a => b\n'
        '=> c =>\n'
        'd'
    )
    original = gp.original
    triggers = gp.triggers
    families = gp.family_map

    assert original['a'] == {'': ''}
    assert original['b'] == {'a:succeeded': 'a:succeeded'}
    assert original['c'] == {'b:succeeded': 'b:succeeded'}
    assert original['d'] == {'c:succeeded': 'c:succeeded'}

    assert triggers['a'] == {'': ([], False)}
    assert triggers['b'] == {'a:succeeded': (['a:succeeded'], False)}
    assert triggers['c'] == {'b:succeeded': (['b:succeeded'], False)}
    assert triggers['d'] == {'c:succeeded': (['c:succeeded'], False)}

    assert not families


def test_parse_graph_with_parameters():
    """Test parsing graphs with parameters."""
    parameterized_parser = GraphParser(
        None, ({'city': ['la_paz']}, {'city': '_%(city)s'}))
    parameterized_parser.parse_graph('a => b<city>')
    original = parameterized_parser.original
    triggers = parameterized_parser.triggers
    families = parameterized_parser.family_map
    assert (
        original == {'a': {'': ''}, 'b_la_paz': {'a:succeeded': 'a:succeeded'}}
    )
    assert (
        triggers == {
            'a': {'': ([], False)},
            'b_la_paz': {'a:succeeded': (['a:succeeded'], False)}
        }
    )
    assert not families


def test_parse_graph_with_invalid_parameters():
    """Test parsing graphs with invalid parameters."""
    parameterized_parser = GraphParser(
        None, ({'city': ['la_paz']}, {'city': '_%(city)s'}))
    with pytest.raises(ParamExpandError):
        # no state in the parameters list
        parameterized_parser.parse_graph('a => b<state>')


def test_inter_workflow_dependence_simple():
    """Test invalid inter-workflow dependence"""
    gp = GraphParser()
    gp.parse_graph(
        """
        a<WORKFLOW::TASK:fail> => b
        c<WORKFLOW::TASK> => d
        """
    )
    assert (
        gp.original ==
        {
            'a': {'': ''},
            'b': {'a:succeeded': 'a:succeeded'},
            'c': {'': ''},
            'd': {'c:succeeded': 'c:succeeded'}
        }
    )
    assert (
        gp.triggers == {
            'a': {'': ([], False)},
            'c': {'': ([], False)},
            'b': {'a:succeeded': (['a:succeeded'], False)},
            'd': {'c:succeeded': (['c:succeeded'], False)}
        }
    )
    assert (
        gp.workflow_state_polling_tasks == {
            'a': (
                'WORKFLOW', 'TASK', 'failed', '<WORKFLOW::TASK:fail>'
            ),
            'c': (
                'WORKFLOW', 'TASK', 'succeeded', '<WORKFLOW::TASK>'
            )
        }
    )
    assert not gp.family_map


def test_line_continuation():
    """Test syntax-driven line continuation."""
    graph1 = "a => b => c"
    graph2 = """a =>
b => c"""
    graph3 = """a => b
=> c"""
    gp1 = GraphParser()
    gp1.parse_graph(graph1)
    gp2 = GraphParser()
    gp2.parse_graph(graph2)
    gp3 = GraphParser()
    gp3.parse_graph(graph3)
    res = {
        'a': {'': ([], False)},
        'c': {'b:succeeded': (['b:succeeded'], False)},
        'b': {'a:succeeded': (['a:succeeded'], False)}
    }
    assert res == gp1.triggers
    assert gp1.triggers == gp2.triggers
    assert gp1.triggers == gp3.triggers
    graph = """foo => bar
        a => b =>"""
    gp = GraphParser()
    pytest.raises(GraphParseError, gp.parse_graph, graph)
    graph = """ => a => b
        foo => bar"""
    gp = GraphParser()
    pytest.raises(GraphParseError, gp.parse_graph, graph)


@pytest.mark.parametrize(
    'graph1, graph2',
    [
        [
            "foo => bar",  # default trigger
            "foo:succeed => bar"
        ],
        [
            "foo => bar",  # default trigger
            "foo:succeeded => bar"
        ],

        [
            "foo => bar",  # repeat trigger
            """foo => bar
            foo => bar"""
        ],
        [
            "foo:finished => bar",  # finish trigger
            "(foo:succeed? | foo:fail?) => bar"
        ],
        [
            """
            bar
            foo => bar:succeed => baz  # ignore qualifier on RHS
            """,
            """
            foo => bar
            bar:succeed => baz
            """
        ],
        [
            """
            foo => bar[1649] => baz
            """,
            """
            foo => bar[1649]
            bar[1649] => baz
            """
        ],
    ]
)
def test_trigger_equivalence(graph1, graph2):
    gp1 = GraphParser()
    gp1.parse_graph(graph1)
    gp2 = GraphParser()
    gp2.parse_graph(graph2)
    assert gp1.triggers == gp2.triggers


@pytest.mark.parametrize(
    'fam_map, fam_graph, member_graph',
    [
        [
            {'FAM': ['m1', 'm2'], 'BAM': ['b1', 'b2']},
            "FAM:succeed-all => BAM",
            """(m1 & m2) => b1
            (m1 & m2) => b2"""
        ],
        [
            {'FAM': ['m1', 'm2']},
            "pre => FAM",
            """pre => m1
            pre => m2"""
        ],
        [
            {'FAM': ['m1', 'm2']},
            "FAM:succeed-all => post",
            "(m1 & m2) => post"
        ],
        [
            {'FAM': ['m1', 'm2']},
            "FAM:succeed-any => post",
            "(m1 | m2) => post",
        ],
        [
            {'FAM': ['m1', 'm2'], 'BAM': ['b1', 'b2']},
            "FAM:fail-any => BAM",
            """(m1:fail | m2:fail) => b1
            (m1:fail | m2:fail) => b2"""
        ],
        [
            {'FAM': ['m1', 'm2']},
            "FAM:finish-all => post",
            "((m1? | m1:fail?) & (m2? | m2:fail?)) => post"
        ]
    ]
)
def test_family_trigger_equivalence(fam_map, fam_graph, member_graph):
    """Test family trigger semantics."""
    gp1 = GraphParser(fam_map)
    gp1.parse_graph(fam_graph)
    gp2 = GraphParser()
    gp2.parse_graph(member_graph)
    assert gp1.triggers == gp2.triggers


def test_parameter_expand():
    """Test graph parameter expansion."""
    fam_map = {
        'FAM_m0': ['fa_m0', 'fb_m0'],
        'FAM_m1': ['fa_m1', 'fb_m1'],
    }
    params = {'m': ['0', '1'], 'n': ['0', '1']}
    templates = {'m': '_m%(m)s', 'n': '_n%(n)s'}
    gp1 = GraphParser(fam_map, (params, templates))
    gp1.parse_graph("""
        pre => foo<m,n> => bar<n>
        bar<n=0> => baz  # specific case
        bar<n-1> => bar<n>  # inter-chunk
        """)
    gp2 = GraphParser()
    gp2.parse_graph("""
        pre => foo_m0_n0 => bar_n0
        pre => foo_m0_n1 => bar_n1
        pre => foo_m1_n0 => bar_n0
        pre => foo_m1_n1 => bar_n1
        bar_n0 => baz
        bar_n0 => bar_n1
        """)
    assert gp1.triggers == gp2.triggers


def test_parameter_specific():
    """Test graph parameter expansion with a specific value."""
    params = {'i': ['0', '1'], 'j': ['0', '1', '2']}
    templates = {'i': '_i%(i)s', 'j': '_j%(j)s'}
    gp1 = GraphParser(family_map=None, parameters=(params, templates))
    gp1.parse_graph("bar<i-1,j> => baz<i,j>\nfoo<i=1,j> => qux")
    gp2 = GraphParser()
    gp2.parse_graph("""
       foo_i1_j0 => qux
       foo_i1_j1 => qux
       foo_i1_j2 => qux
       bar_i0_j0 => baz_i1_j0
       bar_i0_j1 => baz_i1_j1
       bar_i0_j2 => baz_i1_j2""")
    assert gp1.triggers == gp2.triggers


def test_parameter_offset():
    """Test graph parameter expansion with an offset."""
    params = {'i': ['0', '1'], 'j': ['0', '1', '2']}
    templates = {'i': '_i%(i)s', 'j': '_j%(j)s'}
    gp1 = GraphParser(family_map=None, parameters=(params, templates))
    gp1.parse_graph("bar<i-1,j> => baz<i,j>")
    gp2 = GraphParser()
    gp2.parse_graph("""
       bar_i0_j0 => baz_i1_j0
       bar_i0_j1 => baz_i1_j1
       bar_i0_j2 => baz_i1_j2""")
    assert gp1.triggers == gp2.triggers


def test_conditional():
    """Test generation of conditional triggers."""
    gp1 = GraphParser()
    gp1.parse_graph("(foo:start | bar) => baz")
    res = {
        'baz': {
            '(foo:started|bar:succeeded)': (
                ['foo:started', 'bar:succeeded'], False)
        },
        'foo': {
            '': ([], False)
        },
        'bar': {
            '': ([], False)
        }
    }
    assert res == gp1.triggers == res


@pytest.mark.parametrize(
    'graph',
    [
        "foo[-P1Y]<m,n> => bar",
        "foo:fail<m,n> => bar",
        "foo:fail[-P1Y] => bar",
        "foo[-P1Y]:fail<m,n> => bar",
        "foo[-P1Y]<m,n>:fail => bar",
        "foo<m,n>:fail[-P1Y] => bar",
        "foo:fail<m,n>[-P1Y] => bar",
        "<m,n>:fail[-P1Y] => bar",
        "[-P1Y]<m,n> => bar",
        "[-P1Y]<m,n>:fail => bar",
        "bar => foo:fail<m,n>[-P1Y]",
        "foo[-P1Y]baz => bar"
    ]
)
def test_bad_node_syntax(graph):
    """Test that badly formatted graph nodes are detected.

    The correct format is:
      NAME(<PARAMS>)([CYCLE-POINT-OFFSET])(:TRIGGER-TYPE)")
    """
    params = {'m': ['0', '1'], 'n': ['0', '1']}
    templates = {'m': '_m%(m)s', 'n': '_n%(n)s'}
    gp = GraphParser(parameters=(params, templates))
    with pytest.raises(GraphParseError) as cm:
        gp.parse_graph(graph)
    assert "Bad graph node format" in str(cm.value)


def test_spaces_between_tasks_fails():
    """Test that <task> <task> is rejected (i.e. no & or | in between)"""
    gp = GraphParser()
    pytest.raises(
        GraphParseError, gp.parse_graph, "foo bar=> baz")
    pytest.raises(
        GraphParseError, gp.parse_graph, "foo&bar=> ba z")
    pytest.raises(
        GraphParseError, gp.parse_graph, "foo 123=> bar")
    pytest.raises(
        GraphParseError, gp.parse_graph, "foo - 123 baz=> bar")


def test_spaces_between_parameters_fails():
    """Test that <param param> are rejected (i.e. no comma)"""
    gp = GraphParser()
    pytest.raises(
        GraphParseError, gp.parse_graph, "<foo bar> => baz")
    pytest.raises(
        GraphParseError, gp.parse_graph, "<foo=a _bar> => baz")
    pytest.raises(
        GraphParseError, gp.parse_graph, "<foo=a_ bar> => baz")


def test_spaces_between_parameters_passes():
    """Test that <param-1> works, with spaces around the -+ signs"""
    params = {'m': ['0', '1', '2']}
    templates = {'m': '_m%(m)s'}
    gp = GraphParser(parameters=(params, templates))
    gp.parse_graph("<m- 1> => <m>")
    gp.parse_graph("<m -1> => <m>")
    gp.parse_graph("<m - 1> => <m>")
    gp.parse_graph("<m+ 1> => <m>")
    gp.parse_graph("<m +1> => <m>")
    gp.parse_graph("<m + 1> => <m>")


def test_spaces_in_trigger_fails():
    """Test that 'task:a- b' are rejected"""
    gp = GraphParser()
    pytest.raises(
        GraphParseError, gp.parse_graph, "FOO:custom -trigger => baz")
    pytest.raises(
        GraphParseError, gp.parse_graph, "FOO:custom- trigger => baz")
    pytest.raises(
        GraphParseError, gp.parse_graph, "FOO:custom - trigger => baz")


def test_parameter_graph_mixing_offset_and_conditional():
    """Test for bug reported in issue #2608 on GitHub:
    https://github.com/cylc/cylc-flow/issues/2608"""
    params = {'m': ["cat", "dog"]}
    templates = {'m': '_%(m)s'}
    gp = GraphParser(parameters=(params, templates))
    gp.parse_graph("foo<m-1> & baz => foo<m>")
    triggers = {
        'foo_cat': {
            '': (
                [], False
            ),
            'baz:succeeded': (
                ['baz:succeeded'], False
            )
        },
        'foo_dog': {
            'foo_cat:succeeded': (
                ['foo_cat:succeeded'], False
            ),
            'baz:succeeded': (
                ['baz:succeeded'], False
            )
        },
        'baz': {
            '': ([], False)
        }
    }
    assert gp.triggers == triggers


def test_param_expand_graph_parser():
    """Test to validate that the graph parser removes out-of-edge nodes:
    https://github.com/cylc/cylc-flow/pull/3452#issuecomment-677165000"""
    params = {'m': ["cat"]}
    templates = {'m': '_%(m)s'}
    gp = GraphParser(parameters=(params, templates))
    gp.parse_graph("foo => bar<m-1> => baz")
    triggers = {
        'foo': {
            '': ([], False)
        }
    }
    assert gp.triggers == triggers


@pytest.mark.parametrize(
    'expect', ('&', '|', '=>')
)
def test_parse_graph_fails_with_continuation_at_last_line(expect):
    """Fails if last line contains a continuation char.
    """
    parser = GraphParser()
    with pytest.raises(GraphParseError) as raised:
        parser.parse_graph(f't1 => t2 {expect}')
    assert isinstance(raised.value, GraphParseError)
    assert f'Dangling {expect}' in raised.value.args[0]


@pytest.mark.parametrize(
    'before, after',
    product(['&', '|', '=>'], repeat=2)
)
def test_parse_graph_fails_with_too_many_continuations(before, after):
    """Fails if one line ends with continuation char and the next line
    _also_ starts with one.
    """
    parser = GraphParser()
    with pytest.raises(GraphParseError) as raised:
        parser.parse_graph(f'foo & bar {before}\n{after}baz')
    assert isinstance(raised.value, GraphParseError)
    assert 'Consecutive lines end and start' in raised.value.args[0]


def test_task_optional_outputs():
    """Test optional outputs are correctly parsed from graph."""
    OPTIONAL = True
    REQUIRED = False
    gp = GraphParser()
    gp.parse_graph(
        """
        a1 => b1
        a2:succeed => b2
        a3:succeed => b3:succeed

        c1? => d1?
        c2:succeed? => d2?
        c3:succeed? => d3:succeed?

        x:fail? => y

        foo:finish => bar
        """
    )
    for i in range(1, 4):
        for task in (f'a{i}', f'b{i}'):
            assert (
                gp.task_output_opt[(task, TASK_OUTPUT_SUCCEEDED)]
                == (REQUIRED, False, True)
            )

        for task in (f'c{i}', f'd{i}'):
            assert (
                gp.task_output_opt[(task, TASK_OUTPUT_SUCCEEDED)]
                == (OPTIONAL, True, True)
            )

    assert (
        gp.task_output_opt[('x', TASK_OUTPUT_FAILED)]
        == (OPTIONAL, True, True)
    )

    assert (
        gp.task_output_opt[('foo', TASK_OUTPUT_SUCCEEDED)]
        == (OPTIONAL, True, True)
    )

    assert (
        gp.task_output_opt[('foo', TASK_OUTPUT_FAILED)]
        == (OPTIONAL, True, True)
    )


@pytest.mark.parametrize(
    'qual, task_output',
    [
        ('start', TASK_OUTPUT_STARTED),
        ('succeed', TASK_OUTPUT_SUCCEEDED),
        ('fail', TASK_OUTPUT_FAILED),
        ('submit', TASK_OUTPUT_SUBMITTED),
        ('submit-fail', TASK_OUTPUT_SUBMIT_FAILED),
    ]
)
def test_family_optional_outputs(qual, task_output):
    """Test member output optionality inferred from family triggers."""
    fam_map = {
        'FAM': ['f1', 'f2'],
        'BAM': ['b1', 'b2'],
    }
    gp = GraphParser(fam_map)
    gp.parse_graph(
        f"""
        # required
        FAM:{qual}-all => foo
        # optional member
        f2:{task_output}?

        # required
        BAM:{qual}-any => bar
        """
    )
    # -all
    for member in ['f1', 'f2']:
        optional = (member == 'f2')
        assert gp.task_output_opt[(member, task_output)][0] == optional
    # -any
    optional = False
    for member in ['b1', 'b2']:
        assert gp.task_output_opt[(member, task_output)][0] == optional


@pytest.mark.parametrize(
    'graph, error',
    [
        [
            """FAM:succeed-all => foo
            FAM:fail-all => foo""",
            ("must both be optional if both are used (via family trigger"
             " defaults")
        ],
        [
            """FAM:succeed-all => foo
            FAM:succeed-any? => bar""",
            ("can't default to both optional and required (via family trigger"
             " defaults)")
        ],
        [
            "FAM:blargh-all => foo",  # LHS
            "Illegal family trigger"
        ],
        [
            "foo => FAM:blargh-all",  # RHS
            "Illegal family trigger"
        ],
        [
            "FAM => foo",  # bare family on LHS
            "Illegal family trigger"
        ],
    ]
)
def test_family_trigger_errors(graph, error):
    """Test errors via bad family triggers and member output optionality."""
    fam_map = {
        'FAM': ['f1', 'f2']
    }
    gp = GraphParser(fam_map)

    with pytest.raises(GraphParseError) as cm:
        gp.parse_graph(graph)
    assert error in str(cm.value)


@pytest.mark.parametrize(
    'graph, c8error',
    [
        [
            """a:x => b
            a:x? => c""",
            "Output a:x can't be both required and optional",
        ],
        [
            """a? => c
            a => b""",
            "Output a:succeeded can't be both required and optional",
        ],
        [
            """a => c
            a:fail => b""",
            ("must both be optional if both are used"),
        ],
        [
            """a:fail? => b
            a => c""",
            ("must both be optional if both are used"),
        ],
        [
            "a:finish? => b",
            "Pseudo-output a:finished can't be optional",
        ],
    ]
)
def test_task_optional_output_errors_order(
    graph, c8error,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch
):
    """Test optional output errors are raised as expected."""
    gp = GraphParser()
    with pytest.raises(GraphParseError) as cm:
        gp.parse_graph(graph)
    assert c8error in str(cm.value)

    # In Cylc 7 back compat mode these graphs should all pass with no warnings.
    monkeypatch.setattr('cylc.flow.flags.cylc7_back_compat', True)
    caplog.set_level(logging.WARNING, CYLC_LOG)
    gp = GraphParser()
    gp.parse_graph(graph)

    # No warnings logged:
    assert not caplog.messages

    # After graph parsing all Cylc 7 back compat outputs should be optional.
    # (Success outputs are set to required later, in taskdef processing.)
    for (optional, _, _) in gp.task_output_opt.values():
        assert optional


@pytest.mark.parametrize(
    'ftrig',
    GraphParser.fam_to_mem_trigger_map.keys()
)
def test_fail_family_triggers_on_tasks(ftrig):
    gp = GraphParser()
    with pytest.raises(GraphParseError) as cm:
        gp.parse_graph(f"foo:{ftrig} => bar")
        assert (
            str(cm.value).startswith(
                "family trigger on non-family namespace"
            )
        )


@pytest.mark.parametrize(
    'graph, expected_triggers',
    [
        param(
            'a => b & c',
            {'a': [''], 'b': ['a:succeeded'], 'c': ['a:succeeded']},
            id="simple"
        ),
        param(
            'a => (b & c)',
            {'a': [''], 'b': ['a:succeeded'], 'c': ['a:succeeded']},
            id="simple w/ parentheses"
        ),
        param(
            'a => (b & (c & d))',
            {
                'a': [''],
                'b': ['a:succeeded'],
                'c': ['a:succeeded'],
                'd': ['a:succeeded'],
            },
            id="more parentheses"
        ),
    ]
)
def test_RHS_AND(graph: str, expected_triggers: Dict[str, List[str]]):
    """Test '&' operator on right hand side of trigger expression."""
    gp = GraphParser()
    gp.parse_graph(graph)
    triggers = {
        task: list(trigs.keys())
        for task, trigs in gp.triggers.items()
    }
    assert triggers == expected_triggers


@pytest.mark.parametrize(
    'args, err',
    (
        # Error if offset in terminal RHS:
        param((('a', 'b[-P42M]'), {'b[-P42M]'}), 'Invalid cycle point offset'),
        # No error if offset in NON-terminal RHS:
        param((('a', 'b[-P42M]'), {}), None),
        # Don't check the left hand side if this has a non-terminal RHS:
        param((('a &', 'b[-P42M]'), {}), None),
    )
)
def test_proc_dep_pair(args, err):
    """
    Unit tests for _proc_dep_pair.
    """
    gp = GraphParser()
    if err:
        with pytest.raises(GraphParseError, match=err):
            gp._proc_dep_pair(*args)
    else:
        assert gp._proc_dep_pair(*args) is None
