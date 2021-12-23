#!/usr/bin/env bash
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
#-------------------------------------------------------------------------------
# Test workflow graphql interface
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 4
#-------------------------------------------------------------------------------
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

# run workflow
run_ok "${TEST_NAME_BASE}-run" cylc play "${WORKFLOW_NAME}"

# query workflow
TEST_NAME="${TEST_NAME_BASE}-root-queries"
read -r -d '' rootQueries <<_args_
{
  "request_string": "
query {
  workflows(ids: [\"${WORKFLOW_NAME}:running\"]) {
    id
  }
  job(id: \"${WORKFLOW_NAME}//20190101T00/foo/1/*\") {
    id
  }
  jobs(workflows: [\"*\"], ids: [\"*/*/1\"], sort: {keys: [\"id\"], reverse: false}) {
    id
  }
  task(id: \"${WORKFLOW_NAME}//foo\") {
    id
  }
  tasks(sort: {keys: [\"id\"], reverse: false}) {
    id
  }
  taskProxy(id: \"${WORKFLOW_NAME}//20190101T00/foo\") {
    id
  }
  taskProxies(workflows: [\"*\"], ids: [\"*/*\"], isHeld: false, sort: {keys: [\"id\"], reverse: false}) {
    id
  }
  family(id: \"${WORKFLOW_NAME}//FAM\") {
    id
  }
  families(sort: {keys: [\"id\"], reverse: false}) {
    id
  }
  familyProxy(id: \"${WORKFLOW_NAME}//20190101T00/FAM\") {
    id
  }
  familyProxies(workflows: [\"*\"], ids: [\"20190101T00/FAM2\"]) {
    id
  }
  edges(workflows: [\"${WORKFLOW_NAME}\"], sort: {keys: [\"id\"], reverse: false}) {
    id
  }
  nodesEdges(workflows: [\"*\"], ids: [\"*/foo\"], distance: 1, sort: {keys: [\"id\"], reverse: false}) {
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
run_graphql_ok "${TEST_NAME}" "${WORKFLOW_NAME}" "${rootQueries}"

# scrape workflow info from contact file
TEST_NAME="${TEST_NAME_BASE}-contact"
run_ok "${TEST_NAME_BASE}-contact" cylc get-contact "${WORKFLOW_NAME}"

# stop workflow
cylc stop --max-polls=10 --interval=2 --kill "${WORKFLOW_NAME}"

# compare to expectation
cmp_json "${TEST_NAME}-out" "${TEST_NAME_BASE}-root-queries.stdout" << __HERE__
{
    "workflows": [
        {
            "id": "${WORKFLOW_NAME}"
        }
    ],
    "job": {
        "id": "${WORKFLOW_NAME}//20190101T00/foo/1"
    },
    "jobs": [
        {
            "id": "${WORKFLOW_NAME}//20190101T00/baa/1"
        },
        {
            "id": "${WORKFLOW_NAME}//20190101T00/foo/1"
        },
        {
            "id": "${WORKFLOW_NAME}//20190101T00/qar/1"
        },
        {
            "id": "${WORKFLOW_NAME}//20190101T00/qux/1"
        }
    ],
    "task": {
        "id": "${WORKFLOW_NAME}//foo"
    },
    "tasks": [
        {
            "id": "${WORKFLOW_NAME}//baa"
        },
        {
            "id": "${WORKFLOW_NAME}//bar"
        },
        {
            "id": "${WORKFLOW_NAME}//foo"
        },
        {
            "id": "${WORKFLOW_NAME}//qar"
        },
        {
            "id": "${WORKFLOW_NAME}//qaz"
        },
        {
            "id": "${WORKFLOW_NAME}//qux"
        }
    ],
    "taskProxy": {
        "id": "${WORKFLOW_NAME}//20190101T00/foo"
    },
    "taskProxies": [
        {
            "id": "${WORKFLOW_NAME}//20190101T00/baa"
        },
        {
            "id": "${WORKFLOW_NAME}//20190101T00/bar"
        },
        {
            "id": "${WORKFLOW_NAME}//20190101T00/foo"
        },
        {
            "id": "${WORKFLOW_NAME}//20190101T00/qar"
        },
        {
            "id": "${WORKFLOW_NAME}//20190101T00/qaz"
        },
        {
            "id": "${WORKFLOW_NAME}//20190101T00/qux"
        },
        {
            "id": "${WORKFLOW_NAME}//20190201T00/baa"
        },
        {
            "id": "${WORKFLOW_NAME}//20190201T00/foo"
        },
        {
            "id": "${WORKFLOW_NAME}//20190201T00/qar"
        },
        {
            "id": "${WORKFLOW_NAME}//20190201T00/qux"
        }
    ],
    "family": {
        "id": "${WORKFLOW_NAME}//FAM"
    },
    "families": [
        {
            "id": "${WORKFLOW_NAME}//FAM"
        },
        {
            "id": "${WORKFLOW_NAME}//FAM2"
        },
        {
            "id": "${WORKFLOW_NAME}//FAM3"
        },
        {
            "id": "${WORKFLOW_NAME}//FAM4"
        },
        {
            "id": "${WORKFLOW_NAME}//root"
        }
    ],
    "familyProxy": {
        "id": "${WORKFLOW_NAME}//20190101T00/FAM"
    },
    "familyProxies": [
        {
            "id": "${WORKFLOW_NAME}//20190101T00/FAM2"
        }
    ],
    "edges": [
        {
            "id": "${WORKFLOW_NAME}//baa.20190101T00/baa.20190201T00"
        },
        {
            "id": "${WORKFLOW_NAME}//baa.20190101T00/qaz.20190101T00"
        },
        {
            "id": "${WORKFLOW_NAME}//foo.20190101T00/bar.20190101T00"
        },
        {
            "id": "${WORKFLOW_NAME}//foo.20190101T00/foo.20190201T00"
        },
        {
            "id": "${WORKFLOW_NAME}//qar.20190101T00/qar.20190201T00"
        },
        {
            "id": "${WORKFLOW_NAME}//qux.20190101T00/bar.20190101T00"
        },
        {
            "id": "${WORKFLOW_NAME}//qux.20190101T00/qaz.20190101T00"
        },
        {
            "id": "${WORKFLOW_NAME}//qux.20190101T00/qux.20190201T00"
        }
    ],
    "nodesEdges": {
        "nodes": [
            {
                "id": "${WORKFLOW_NAME}//20190101T00/bar"
            },
            {
                "id": "${WORKFLOW_NAME}//20190101T00/foo"
            },
            {
                "id": "${WORKFLOW_NAME}//20190201T00/foo"
            }
        ],
        "edges": [
            {
                "id": "${WORKFLOW_NAME}//foo.20190101T00/bar.20190101T00"
            },
            {
                "id": "${WORKFLOW_NAME}//foo.20190101T00/foo.20190201T00"
            }
        ]
    }
}
__HERE__

purge
