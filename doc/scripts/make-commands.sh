#!/bin/bash

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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

CYLC=../bin/cylc

cat > commands.tex <<END
\label{help}
\lstinputlisting{cylc.txt}
\subsection{Command Categories}
END

for CAT in $( $CYLC categories ); do
	cat >> commands.tex <<END
\subsubsection{$CAT}
\label{$CAT}
\lstinputlisting{categories/${CAT}.txt}
END
done

cat >> commands.tex <<END
\subsection{Commands}
END

for COMMAND in $( $CYLC commands ); do
	cat >> commands.tex <<END
\subsubsection{$COMMAND}
\label{$COMMAND}
\lstinputlisting{commands/${COMMAND}.txt}
END
done

