#!/bin/bash

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & contributors
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

# Create cylc-version.txt and commands.tex for inclusion in LaTeX doc.

CYLC=$(dirname $0)/../../../../bin/cylc

$CYLC --version > cylc-version.txt

cat > commands.tex <<END
\label{help}
\begin{lstlisting}
$($CYLC --help)
\end{lstlisting}
\subsection{Command Categories}
END

for CAT in $($CYLC categories); do
	cat >> commands.tex <<END
\subsubsection{$CAT}
\label{$CAT}
\begin{lstlisting}
$($CYLC $CAT --help)
\end{lstlisting}
END
done

cat >> commands.tex <<END
\subsection{Commands}
END

for COM in $($CYLC commands); do
	cat >> commands.tex <<END
\subsubsection{$COM}
\label{$COM}
\begin{lstlisting}
$($CYLC $COM --help)
\end{lstlisting}
END
done
