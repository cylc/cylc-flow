
EVENT=$1
SUITE=$2
TASK=$3
MSG="$4"

printf '%15s' $EVENT >> $EVNTLOG
echo -e "\t$TASK\t\"$MSG\"" >> $EVNTLOG

