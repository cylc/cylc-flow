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
skip_all 'TODO: awaiting re-write'
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
            "id": "~${USER}/${WORKFLOW_NAME}"
        }
    ],
    "job": {
        "id": "~${USER}/${WORKFLOW_NAME}//20190101T00/foo/1"
    },
    "jobs": [
        {
            "id": "~${USER}/${WORKFLOW_NAME}//20190101T00/baa/1"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//20190101T00/foo/1"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//20190101T00/qar/1"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//20190101T00/qux/1"
        }
    ],
    "task": {
        "id": "~${USER}/${WORKFLOW_NAME}//foo"
    },
    "tasks": [
        {
            "id": "~${USER}/${WORKFLOW_NAME}//baa"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//bar"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//foo"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//qar"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//qaz"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//qux"
        }
    ],
    "taskProxy": {
        "id": "~${USER}/${WORKFLOW_NAME}//20190101T00/foo"
    },
    "taskProxies": [
        {
            "id": "~${USER}/${WORKFLOW_NAME}//20190101T00/baa"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//20190101T00/bar"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//20190101T00/foo"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//20190101T00/qar"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//20190101T00/qaz"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//20190101T00/qux"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//20190201T00/baa"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//20190201T00/foo"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//20190201T00/qar"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//20190201T00/qux"
        }
    ],
    "family": {
        "id": "~${USER}/${WORKFLOW_NAME}//FAM"
    },
    "families": [
        {
            "id": "~${USER}/${WORKFLOW_NAME}//FAM"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//FAM2"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//FAM3"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//FAM4"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//root"
        }
    ],
    "familyProxy": {
        "id": "~${USER}/${WORKFLOW_NAME}//20190101T00/FAM"
    },
    "familyProxies": [
        {
            "id": "~${USER}/${WORKFLOW_NAME}//20190101T00/FAM2"
        }
    ],
    "edges": [
        {
            "id": "~${USER}/${WORKFLOW_NAME}//baa.20190101T00/baa.20190201T00"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//baa.20190101T00/qaz.20190101T00"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//foo.20190101T00/bar.20190101T00"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//foo.20190101T00/foo.20190201T00"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//qar.20190101T00/qar.20190201T00"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//qux.20190101T00/bar.20190101T00"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//qux.20190101T00/qaz.20190101T00"
        },
        {
            "id": "~${USER}/${WORKFLOW_NAME}//qux.20190101T00/qux.20190201T00"
        }
    ],
    "nodesEdges": {
        "nodes": [
            {
                "id": "~${USER}/${WORKFLOW_NAME}//20190101T00/bar"
            },
            {
                "id": "~${USER}/${WORKFLOW_NAME}//20190101T00/foo"
            },
            {
                "id": "~${USER}/${WORKFLOW_NAME}//20190201T00/foo"
            }
        ],
        "edges": [
            {
                "id": "~${USER}/${WORKFLOW_NAME}//foo.20190101T00/bar.20190101T00"
            },
            {
                "id": "~${USER}/${WORKFLOW_NAME}//foo.20190101T00/foo.20190201T00"
            }
        ]
    }
}
__HERE__

purge
