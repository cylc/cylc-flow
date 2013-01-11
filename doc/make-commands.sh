#!/bin/bash

echo "Generating command help"

CYLC=../bin/cylc

mkdir -p new-command-usage

$CYLC help > new-command-usage/help.txt

echo "Categories"
for CAT in $( $CYLC categories ); do
	echo " o $CAT"
	$CYLC help $CAT > new-command-usage/${CAT}.txt
done

echo "Commands"
for COMMAND in $( $CYLC commands ); do
	echo " + $COMMAND"
	$CYLC $COMMAND --help > new-command-usage/${COMMAND}.txt
done

# regenerate commands.tex only if command usage help has changed 

UPDATE=false
diff -r new-command-usage command-usage >/dev/null || UPDATE=true
[[ ! -f commands.tex ]] && UPDATE=true

if $UPDATE; then 
	echo "Command help changed: updating commands.tex"
else
	echo "Command help unchanged"
	exit 0
fi

rm -rf command-usage/
mv new-command-usage/ command-usage

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

