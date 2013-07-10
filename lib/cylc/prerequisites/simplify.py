import re
import ast
import copy


class conditional_simplifier( object ):
    
    def __init__( self, expr, clean ):
        self.raw_expression = expr
        self.clean_list = clean
        self.nested_expr = self.format_expr( self.raw_expression )

    def listify( self, message ):
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
        cleaned = self.nested_expr
        for item in self.clean_list:
            cleaned = self.clean_expr( cleaned, item )
        cleaned = self.flatten_nested_expr( cleaned )
        return cleaned        

    def nest_by_oper( self, nest_me, oper ):
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
        cleaned = copy.deepcopy( nested_list )
        found = None
        if len(cleaned) == 1:
            return cleaned
        for i in range(0, len(cleaned)):
            if isinstance(cleaned[i], list):
                cleaned[i] = self.clean_expr(cleaned[i], criteria)
            if cleaned[i] == criteria:
                found = i
        if found is not None:
            if found == 0:
                return cleaned[2]
            elif found == 2:
                return cleaned[0]
        else:
            return cleaned

    def format_expr( self, expr ):
        listified = self.listify( expr )
        bracketed = self.get_bracketed( listified )
        nested_by_and = self.nest_by_oper( bracketed, "&" )
        nested_by_or = self.nest_by_oper( nested_by_and, "|" )
        return nested_by_or
    
    def flatten_nested_expr( self, expr ):
        flattened = copy.deepcopy( expr )
        for i in range(0,len(flattened)):
            if isinstance(flattened[i], list):
                flattened[i] = self.flatten_nested_expr( flattened[i] )
        if isinstance(flattened, list):
            flattened = (" ").join(flattened)
        flattened = "(" + flattened
        flattened += ")"
        return flattened


