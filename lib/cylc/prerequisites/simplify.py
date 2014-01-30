#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re
import ast
import copy


class conditional_simplifier( object ):
    """A class to simplify logical expressions"""

    def __init__( self, expr, clean ):
        self.raw_expression = expr
        self.clean_list = clean
        self.nested_expr = self.format_expr( self.raw_expression )

    def listify( self, message ):
        """Convert a string containing a logical expression to a list"""
        message = message.replace("'","\"")
        RE_CONDITIONALS = "(&|\||\(|\))"
        tokenised = re.split("(&|\||\(|\))", message)
        listified = ["["]
        for item in tokenised:
            if item.strip() != "" and item.strip() not in ["(",")"]:
                listified.append("'" + item.strip() + "',")
            elif item.strip() == "(":
                listified.append("[")
            elif item.strip() == ")":
                if listified[-1].endswith(","):
                    listified[-1] = listified[-1][0:-1]
                listified.append("],")
        if listified[-1] == "],":
            listified[-1] = "]"
        listified.append("]")
        listified = (" ").join(listified)
        listified = ast.literal_eval(listified)
        return listified

    def get_bracketed( self, nest_me ):
        """Nest a list according to any brackets in it"""
        start = 0
        finish = len(nest_me)
        indices = range(0, len(nest_me))
        for i in indices:
            if nest_me[i] == "(":
                start = i
                break
        else:
            return nest_me
        indices.reverse()
        for i in indices:
            if nest_me[i] == ")":
                finish = i
                break
        bracket_nested = nest_me[0:start+1]
        bracket_nested.append(self.get_bracketed(nest_me[start+1:finish]))
        bracket_nested.extend(nest_me[finish:len(nest_me)])
        return bracket_nested

    def get_cleaned( self ):
        """Return the simplified logical expression"""
        cleaned = self.nested_expr
        for item in self.clean_list:
            cleaned = self.clean_expr( cleaned, item )
        cleaned = self.flatten_nested_expr( cleaned )
        return cleaned

    def nest_by_oper( self, nest_me, oper ):
        """Nest a list based on a specified logical operation"""
        found = False
        for i in range(0,len(nest_me)):
            if isinstance(nest_me[i], list):
                nest_me[i] = self.nest_by_oper(nest_me[i], oper)
            if nest_me[i] == oper:
                found = i
                break
        if len(nest_me) <= 3:
            return nest_me
        if found:
            nested = nest_me[0:found-1]
            nested += [nest_me[found-1:found+2]]
            if (found+2) < len(nest_me):
                nested += nest_me[found+2:]
            return self.nest_by_oper(nested, oper)
        else:
            return nest_me

    def clean_expr( self, nested_list, criteria ):
        """Return a list with entries specified by 'critria' removed"""
        cleaned = copy.deepcopy( nested_list )
        # Make sure that we don't have extraneous nesting.
        while (isinstance(cleaned, list) and len(cleaned) == 1 and
               isinstance(cleaned[0], list)):
            cleaned = cleaned[0]

        # Recurse through the nested list and remove criteria.
        found = None
        if isinstance(cleaned, str) or len(cleaned)==1:
            if cleaned == criteria:
                return ""
            else:
                return cleaned
        for i in range(0, len(cleaned)):
            if isinstance(cleaned[i], list):
                cleaned[i] = self.clean_expr(cleaned[i], criteria)
            if cleaned[i] == criteria:
                found = i
        if found is not None:
            if found == 0:
                return self.clean_expr(cleaned[2], criteria)
            elif found == 2:
                return self.clean_expr(cleaned[0], criteria)
        else:
            return cleaned

    def format_expr( self, expr ):
        """Carry out list conversion and nesting of a logical expression in
        the correct order."""
        listified = self.listify( expr )
        bracketed = self.get_bracketed( listified )
        nested_by_and = self.nest_by_oper( bracketed, "&" )
        nested_by_or = self.nest_by_oper( nested_by_and, "|" )
        return nested_by_or

    def flatten_nested_expr( self, expr ):
        """Convert a logical expression in a nested list back to a string"""
        flattened = copy.deepcopy( expr )
        for i in range(0,len(flattened)):
            if isinstance(flattened[i], list):
                flattened[i] = self.flatten_nested_expr( flattened[i] )
        if isinstance(flattened, list):
            flattened = (" ").join(flattened)
        flattened = "(" + flattened
        flattened += ")"
        return flattened


