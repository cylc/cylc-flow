#!/usr/bin/env python

import sys
import json

output = sys.stdin.read()
exp_output = json.dumps(
{
    "f.20000102T0000Z": {
        "prerequisites": [
            ["0 & 1 & (2 | (3 & 4)) & 5", False],
            ["\t0 = a.20000102T0000Z succeeded", False],
            ["\t1 = b.20000102T0000Z succeeded", False],
            ["\t2 = c.20000102T0000Z succeeded", False],
            ["\t3 = d.20000102T0000Z succeeded", False],
            ["\t4 = e.20000102T0000Z succeeded", False],
            ["\t5 = f.20000101T0000Z succeeded", False]
        ],
        "outputs": [
            ["f.20000102T0000Z submitted", False],
            ["f.20000102T0000Z started", False],
            ["f.20000102T0000Z succeeded", False]
        ],
        "extras": {},
        "descriptions": {
            "description": "",
            "title": ""
        }
    }
})

def is_valid_json(possiblejson):
    """Tests if input is a valid JSON data structure"""
    try:
        valid_json_expression = json.loads(possiblejson)
    except ValueError, e:
        return False
    return True

if is_valid_json(output):
    if cmp(json.loads(output),json.loads(exp_output)) == 0:
        sys.exit()
    else:
        sys.exit("Output in JSON format but not as expected ... not ok")
else:
    sys.exit("Output not in JSON format ... not ok")
