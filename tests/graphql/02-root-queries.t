#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
#-------------------------------------------------------------------------------
# Test suite graphql interface
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 4
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

# run suite
run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}"

# query suite
TEST_NAME="${TEST_NAME_BASE}-root-queries"
ID_DELIM="$(python -c 'from cylc.flow import ID_DELIM;print(ID_DELIM)')"
read -r -d '' rootQueries <<_args_
{
  "request_string": "
query {
  workflows(ids: [\"*${ID_DELIM}${SUITE_NAME}:running\"]) {
    id
  }
  job(id: \"${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}20190101T00${ID_DELIM}foo${ID_DELIM}1\") {
    id
  }
  jobs(workflows: [\"*${ID_DELIM}*\"], ids: [\"*${ID_DELIM}*${ID_DELIM}1\"], sort: {keys: [\"id\"], reverse: false}) {
    id
  }
  task(id: \"${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}foo\") {
    id
  }
  tasks(sort: {keys: [\"id\"], reverse: false}) {
    id
  }
  taskProxy(id: \"${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}20190101T00${ID_DELIM}foo\") {
    id
  }
  taskProxies(workflows: [\"*${ID_DELIM}*\"], ids: [\"*${ID_DELIM}*\"], isHeld: false, sort: {keys: [\"id\"], reverse: false}) {
    id
  }
  family(id: \"${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}FAM\") {
    id
  }
  families(sort: {keys: [\"id\"], reverse: false}) {
    id
  }
  familyProxy(id: \"${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}20190101T00${ID_DELIM}FAM\") {
    id
  }
  familyProxies(workflows: [\"*${ID_DELIM}*\"], ids: [\"20190101T00${ID_DELIM}FAM2\"]) {
    id
  }
  edges(workflows: [\"${USER}${ID_DELIM}${SUITE_NAME}\"], sort: {keys: [\"id\"], reverse: false}) {
    id
  }
  nodesEdges(workflows: [\"*${ID_DELIM}*\"], ids: [\"foo\"], distance: 1, sort: {keys: [\"id\"], reverse: false}) {
    nodes {
      id
    }
    edges {
      id
    }
  }
}",
  "variables": null
}
_args_
run_graphql_ok "${TEST_NAME}" "${SUITE_NAME}" "${rootQueries}"

# scrape suite info from contact file
TEST_NAME="${TEST_NAME_BASE}-contact"
run_ok "${TEST_NAME_BASE}-contact" cylc get-contact "${SUITE_NAME}"

# stop suite
cylc stop --max-polls=10 --interval=2 --kill "${SUITE_NAME}"

# compare to expectation
cat > expected << __HERE__
{
    "workflows": [
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}"
        }
    ],
    "job": {
        "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}20190101T00${ID_DELIM}foo${ID_DELIM}1"
    },
    "jobs": [
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}20190101T00${ID_DELIM}baa${ID_DELIM}1"
        },
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}20190101T00${ID_DELIM}foo${ID_DELIM}1"
        },
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}20190101T00${ID_DELIM}qar${ID_DELIM}1"
        },
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}20190101T00${ID_DELIM}qux${ID_DELIM}1"
        }
    ],
    "task": {
        "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}foo"
    },
    "tasks": [
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}baa"
        },
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}bar"
        },
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}foo"
        },
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}qar"
        },
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}qaz"
        },
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}qux"
        }
    ],
    "taskProxy": {
        "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}20190101T00${ID_DELIM}foo"
    },
    "taskProxies": [
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}20190101T00${ID_DELIM}baa"
        },
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}20190101T00${ID_DELIM}bar"
        },
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}20190101T00${ID_DELIM}foo"
        },
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}20190101T00${ID_DELIM}qar"
        },
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}20190101T00${ID_DELIM}qaz"
        },
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}20190101T00${ID_DELIM}qux"
        }
    ],
    "family": {
        "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}FAM"
    },
    "families": [
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}FAM"
        },
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}FAM2"
        },
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}FAM3"
        },
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}FAM4"
        },
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}FAM5"
        },
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}root"
        }
    ],
    "familyProxy": {
        "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}20190101T00${ID_DELIM}FAM"
    },
    "familyProxies": [
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}20190101T00${ID_DELIM}FAM2"
        }
    ],
    "edges": [
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}@wall_clock.20190101T00${ID_DELIM}foo.20190101T00"
        },
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}@wall_clock.20190101T00${ID_DELIM}qux.20190101T00"
        },
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}baa.20190101T00${ID_DELIM}qaz.20190101T00"
        },
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}foo.20190101T00${ID_DELIM}bar.20190101T00"
        },
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}qux.20190101T00${ID_DELIM}bar.20190101T00"
        },
        {
            "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}qux.20190101T00${ID_DELIM}qaz.20190101T00"
        }
    ],
    "nodesEdges": {
        "nodes": [
            {
                "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}20190101T00${ID_DELIM}bar"
            },
            {
                "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}20190101T00${ID_DELIM}foo"
            }
        ],
        "edges": [
            {
                "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}@wall_clock.20190101T00${ID_DELIM}foo.20190101T00"
            },
            {
                "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}foo.20190101T00${ID_DELIM}bar.20190101T00"
            }
        ]
    }
}
__HERE__
cmp_json "${TEST_NAME}-out" \
    "${TEST_NAME_BASE}-root-queries.stdout" \
    "$(cat expected)"

purge_suite "${SUITE_NAME}"

exit
