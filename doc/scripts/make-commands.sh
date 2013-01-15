#!/bin/bash

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
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

echo "Generating command help"

CYLC=../bin/cylc

NEWCOMMANDHELP=$( mktemp -d )

$CYLC help > $NEWCOMMANDHELP/help.txt

echo "Categories"
for CAT in $( $CYLC categories ); do
	echo " o $CAT"
	$CYLC help $CAT > $NEWCOMMANDHELP/${CAT}.txt
done

echo "Commands"
for COMMAND in $( $CYLC commands ); do
	echo " + $COMMAND"
	$CYLC $COMMAND --help > $NEWCOMMANDHELP/${COMMAND}.txt
done

# regenerate commands.tex only if command usage help has changed 

if [[ ! -f commands.tex ]]; then
    echo "No existing command help file, generating commands.tex"
elif ! diff -r $NEWCOMMANDHELP command-usage >/dev/null 2>&1; then
    # diff returns 0 if target files do not differ
	echo "Command help changed, I will regenerate commands.tex"
else
	echo "Command help unchanged, not regenerating commands.tex"
	exit 0
fi

rm -rf command-usage/
cp -r $NEWCOMMANDHELP/ command-usage

cat > commands.tex <<END
\label{help}
\lstinputlisting{command-usage/help.txt}
\subsection{Command Categories}
END

for CAT in $( $CYLC categories ); do
	cat >> commands.tex <<END
\subsubsection{$CAT}
\label{$CAT}
\lstinputlisting{command-usage/${CAT}.txt}
END
done

cat >> commands.tex <<END
\subsection{Commands}
END

for COMMAND in $( $CYLC commands ); do
	cat >> commands.tex <<END
\subsubsection{$COMMAND}
\label{$COMMAND}
\lstinputlisting{command-usage/${COMMAND}.txt}
END
done

