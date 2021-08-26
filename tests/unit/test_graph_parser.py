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


import pytest
import logging

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


def test_parse_graph_fails_if_starts_with_arrow():
    """Test fail when the graph starts with an arrow."""
    with pytest.raises(GraphParseError):
        GraphParser().parse_graph("=> b")


def test_parse_graph_fails_if_ends_with_arrow():
    """Test fail when the graph ends with an arrow."""
    with pytest.raises(GraphParseError):
        GraphParser().parse_graph("a =>")


def test_parse_graph_fails_with_spaces_in_task_name():
    """Test fail when the task name contains spaces."""
    with pytest.raises(GraphParseError):
        GraphParser().parse_graph("a b => c")


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


def test_parse_graph_fails_suicide_on_left():
    """Test fail with suicide trigger on the left."""
    with pytest.raises(GraphParseError) as cm:
        GraphParser().parse_graph("!foo => bar")
    assert (
        "Suicide markers must be on the right of a trigger:"
        in str(cm.value)
    )


def test_parse_graph_fails_mismatched_paren():
    """Test fail mismatched parentheses."""
    with pytest.raises(GraphParseError) as cm:
        GraphParser().parse_graph("( foo & bar => baz")
    assert (
        "Mismatched parentheses in:" in str(cm.value)
    )


def test_parse_graph_fails_with_suicide_and_not_suicide():
    """Test graph parser fails with both "expr => !foo"
    and "expr => !foo" in the same graph."""
    with pytest.raises(GraphParseError):
        GraphParser().parse_graph(
            """(a | b & c) => d
               foo => bar
               (a | b & c) => !d
            """)


def test_parse_graph_simple():
    """Test parsing graphs."""
    # added white spaces and comments to show that these change nothing

    gp = GraphParser()
    gp.parse_graph('a => b\n  \n# this is a comment\n')

    original = gp.original
    triggers = gp.triggers
    families = gp.family_map

    assert (
        {'a': {'': ''}, 'b': {'a:succeeded': 'a:succeeded'}}
        == original
    )

    assert (
        {
            'a': {'': ([], False)},
            'b': {'a:succeeded': (['a:succeeded'], False)}
        }
        == triggers
    )
    assert not families


def test_parse_graph_simple_with_break_line_01():
    """Test parsing graphs."""
    gp = GraphParser()
    gp.parse_graph('a => b\n'
                   '=> c')
    original = gp.original
    triggers = gp.triggers
    families = gp.family_map

    assert ({'': ''} == original['a'])
    assert ({'a:succeeded': 'a:succeeded'} == original['b'])
    assert ({'b:succeeded': 'b:succeeded'} == original['c'])

    assert ({'': ([], False)} == triggers['a'])
    assert (
        {'a:succeeded': (['a:succeeded'], False)} == triggers['b'])
    assert (
        {'b:succeeded': (['b:succeeded'], False)} == triggers['c'])

    assert not families


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

    assert ({'': ''} == original['a'])
    assert ({'a:succeeded': 'a:succeeded'} == original['b'])
    assert ({'b:succeeded': 'b:succeeded'} == original['c'])
    assert ({'c:succeeded': 'c:succeeded'} == original['d'])

    assert ({'': ([], False)} == triggers['a'])
    assert (
        {'a:succeeded': (['a:succeeded'], False)} == triggers['b'])
    assert (
        {'b:succeeded': (['b:succeeded'], False)} == triggers['c'])
    assert (
        {'c:succeeded': (['c:succeeded'], False)} == triggers['d'])

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
        {'a': {'': ''}, 'b_la_paz': {'a:succeeded': 'a:succeeded'}}
        == original
    )
    assert (
        {'a': {'': ([], False)},
         'b_la_paz': {'a:succeeded': (['a:succeeded'], False)}}
        == triggers
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
    gp.parse_graph('a<WORKFLOW::TASK:fail> => b')
    original = gp.original
    triggers = gp.triggers
    families = gp.family_map
    workflow_state_polling_tasks = gp.workflow_state_polling_tasks
    assert (
        {'a': {'': ''}, 'b': {'a:succeeded': 'a:succeeded'}}
        == original
    )
    assert (
        {'a': {'': ([], False)},
         'b': {'a:succeeded': (['a:succeeded'], False)}}
        == triggers
    )
    assert (
        ('WORKFLOW', 'TASK', 'failed', '<WORKFLOW::TASK:fail>')
        == workflow_state_polling_tasks['a']
    )
    assert not families


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
    assert (gp1.triggers == res)
    assert (gp1.triggers == gp2.triggers)
    assert (gp1.triggers == gp3.triggers)
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
        ]
    ]
)
def test_trigger_equivalence(graph1, graph2):
    gp1 = GraphParser()
    gp1.parse_graph(graph1)
    gp2 = GraphParser()
    gp2.parse_graph(graph2)
    assert (gp1.triggers == gp2.triggers)


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
    assert (gp1.triggers == gp2.triggers)


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
    assert (gp1.triggers == gp2.triggers)


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
    assert (gp1.triggers == gp2.triggers)


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
    assert (gp1.triggers == res)


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
    assert "bad graph node format" in str(cm.value)


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
    assert (gp.triggers == triggers)


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
    assert (gp.triggers == triggers)


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
                == REQUIRED
            )

        for task in (f'c{i}', f'd{i}'):
            assert (
                gp.task_output_opt[(task, TASK_OUTPUT_SUCCEEDED)]
                == OPTIONAL
            )

    assert (
        gp.task_output_opt[('x', TASK_OUTPUT_FAILED)]
        == OPTIONAL
    )

    assert (
        gp.task_output_opt[('foo', TASK_OUTPUT_SUCCEEDED)]
        == OPTIONAL
    )

    assert (
        gp.task_output_opt[('foo', TASK_OUTPUT_FAILED)]
        == OPTIONAL
    )


@pytest.mark.parametrize(
    'fam_qual, task_out',
    [
        ('start', TASK_OUTPUT_STARTED),
        ('finish', TASK_OUTPUT_SUCCEEDED),
        ('succeed', TASK_OUTPUT_SUCCEEDED),
        ('submit', TASK_OUTPUT_SUBMITTED),
        ('submit-fail', TASK_OUTPUT_SUBMIT_FAILED),
        ('fail', TASK_OUTPUT_FAILED)
    ]
)
def test_family_optional_outputs(fam_qual, task_out):
    """Test that member output optionality is correctly inferred
    from family triggers."""
    fam_map = {
        'FAM': ['f1', 'f2'],
        'BAM': ['b1', 'b2'],
    }
    gp = GraphParser(fam_map)
    gp.parse_graph(
        f"""
        FAM:{fam_qual}-all => f
        f2:{task_out}?
        BAM:{fam_qual}-any => b
        """
    )

    optional = (fam_qual == "finish")
    for member in ['f1', 'f2']:
        assert gp.memb_output_opt[(member, task_out)] == optional
    assert gp.task_output_opt[('f2', task_out)]

    optional = (fam_qual != "start")
    for member in ['b1', 'b2']:
        assert gp.memb_output_opt[(member, task_out)] == optional


@pytest.mark.parametrize(
    'graph, error',
    [
        [
            "a => b | c",
            "Illegal OR on right side"
        ],
        [
            "foo && bar => baz",
            "The graph AND operator is '&'"
        ],
        [
            "foo || bar => baz",
            "The graph OR operator is '|'"
        ]
    ]

)
def test_syntax_error(graph, error):
    """Test optional output errors are raised as expected."""
    gp = GraphParser()
    with pytest.raises(GraphParseError) as cm:
        gp.parse_graph(graph)
    assert error in str(cm.value)


@pytest.mark.parametrize(
    'graph, c8error, c7backcompat',
    [
        [
            """a:x => b
            a:x? => c""",
            "Output a:x is required so it can't also be optional.",
            "making it optional."
        ],
        [
            """a? => c
            a => b""",
            "Output a:succeeded is optional so it can't also be required.",
            "making it optional."

        ],
        [
            """a => c
            a:fail => b""",
            ("Output a:succeeded is required so a:failed "
             "can't be required."),
            "making both optional."
        ],
        [
            """a:finish => b
            a => c""",
            "Output a:succeeded is optional so it can't also be required.",
            "making it optional."

        ],
        [
            """a => c
            a:finish => b""",
            "Output a:succeeded is required so it can't also be optional.",
            "making it optional."

        ],
        # The next case is different to the previous case because
        # :succeeded is processed first in the :finished pseudo-output.
        [
            """a:fail => c
            a:finish => b""",
            "Output a:failed is required so a:succeeded can't be optional.",
            "making both optional."
        ],
        [
            """a:finish => b
            a:fail => c""",
            "Output a:failed is optional so it can't also be required.",
            "making it optional."

        ],
    ]
)
def test_task_optional_output_errors_order(
    graph, c8error, c7backcompat,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch
):
    """Test optional output errors are raised as expected.

    Parse the graph lines separately (as for separate graph strings) to ensure
    that order is preserved (the error is different depending on whether an
    output gets set to optional or required first).
    """
    graph1, graph2 = graph.split('\n')
    gp1 = GraphParser()
    gp1.parse_graph(graph1)
    gp2 = GraphParser(task_output_opt=gp1.task_output_opt)
    with pytest.raises(GraphParseError) as cm:
        gp2.parse_graph(graph2)
    assert c8error in str(cm.value)

    monkeypatch.setattr('cylc.flow.flags.cylc7_back_compat', True)
    caplog.set_level(logging.WARNING, CYLC_LOG)
    gp1 = GraphParser()
    gp1.parse_graph(graph1)
    gp2 = GraphParser(task_output_opt=gp1.task_output_opt)
    gp2.parse_graph(graph2)
    assert c8error in caplog.messages[0]
    assert c7backcompat in caplog.messages[0]


def test_fail_bare_family_trigger():
    """Test that "FAM => bar" (no :succeed-all etc.) raises an error."""
    gp = GraphParser({'FAM': ['m1', 'm2']})
    with pytest.raises(GraphParseError) as cm:
        gp.parse_graph("FAM => f")
    assert (
        str(cm.value).startswith("Bad family trigger in")
    )


@pytest.mark.parametrize(
    'ftrig',
    GraphParser.fam_to_mem_trigger_map.keys()
)
def test_fail_family_trigger_on_task(ftrig):
    gp = GraphParser()
    with pytest.raises(GraphParseError) as cm:
        gp.parse_graph(f"foo:{ftrig} => bar")
        assert (
            str(cm.value).startswith(
                "family trigger on non-family namespace"
            )
        )
