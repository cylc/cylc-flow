#!/usr/bin/env bash
# 
# This is an experimental bash script to replace the python 'cylc' command
#
function print_version() {
    echo "Placeholder for calling the cylc.version script (python)"
}

function init_dirs() {
    #CYLC_NS=$(basename $0)
    cylc_dir_lib="$(dirname "$dir")"
    CYLC_DIR=$cylc_dir_lib # wrong
    CYLC_HOME_BIN=$(cd $(dirname $0) && pwd)
    # Rose has a 'canonicalize link' step here,
    # is this needed for cylc? 
    CYLC_HOME=$(dirname $CYLC_HOME_BIN)
    
    # TODO
    # This would actually be CYLC_NS=$(basename $0) in the final version
    CYLC_NS="cylc"
    
    PATH=$(path_lead "${PATH:-}" "$CYLC_HOME_BIN")
    PYTHONPATH=$(path_lead "${PYTHONPATH:-}" "$CYLC_HOME/lib/")
    
    export PATH PYTHONPATH
}

function cylc_usage() {
    echo "Placeholder for calling and printing the main help script."
}

function help_util() {
    echo "Call help function for: $UTIL"
    local NAME=$1
    local COMMAND=$CYLC_HOME_BIN/$CYLC_NS-$NAME
    if [[ ! -r $COMMAND ]]; then
        echo "$1: utility not found." >&2
        return 1
    fi
    local ALIAS=$(get_alias $NAME)
    if [[ -n $ALIAS ]]; then
        COMMAND=$CYLC_HOME_BIN/$CYLC_NS-$ALIAS
        COMMAND=${COMMAND%% *}
    fi
    
    #exec $COMMAND --help
    
    
    case $(head -1 -- $COMMAND) in
    *bash*)
        awk '{
            if (/^# NAME/) {
                do {print substr($0, 3)} while (getline && !/^#----------/);
            }
        }' $COMMAND | ${PAGER:-less}
        ;;
    *python*)
        $COMMAND --help | ${PAGER:-less} # FIXME: not too pretty at the moment
        ;;
    esac
    return
}

function get_alias() {
    local NAME=$1
    local ALIAS=$(sed '/^#/d' $CYLC_HOME_BIN/$CYLC_NS-$NAME || true)
    if [[ $(wc -l <<<"$ALIAS") == 1 ]] \
        && grep -q "^exec \$(dirname \$0)/$CYLC_NS-.* \"\$@\"\$" <<<"$ALIAS"
    then
        ALIAS=${ALIAS#"exec \$(dirname \$0)/$CYLC_NS-"}
        ALIAS=${ALIAS%' "$@"'}
        $ALIAS
    fi
}

# Ensure that ITEM_STR is at the beginning of PATH_STR
function path_lead() {
    local PATH_STR=$1
    local ITEM_STR=$2
    if [[ -z ${PATH_STR:-} ]]; then
        echo "$ITEM_STR"
    elif [[ "$PATH_STR" != "$ITEM_STR" && "$PATH_STR" != $ITEM_STR:* ]]; then
        while [[ "$PATH_STR" == *:$ITEM_STR ]]; do
            PATH_STR=${PATH_STR%:$ITEM_STR}
        done
        while [[ "$PATH_STR" == *:$ITEM_STR:* ]]; do
            local PATH_HEAD=${PATH_STR%:$ITEM_STR:*}
            local PATH_TAIL=${PATH_STR##*:$ITEM_STR:}
            PATH_STR="$PATH_HEAD:$PATH_TAIL"
        done
        echo "$ITEM_STR:$PATH_STR"
    else
        echo "$PATH_STR"
    fi
}

init_dirs

UTIL="help"
if (($# > 0)); then
    UTIL=$1
    shift 1
fi

case $UTIL in
help|h|?|--help|-h)
    if (($# == 0)); then
        {
            print_version
            cylc_usage
            echo
            echo "$CYLC_NS provides the following commands:"
            for U in $(cd $CYLC_HOME_BIN && ls $CYLC_NS-*); do
                # echo $U
                NAME=$(sed "s/^$CYLC_NS-\\(.*\\)\$/\1/" <<<$U)
                ALIAS=$(get_alias $NAME)
                if [[ -n $ALIAS ]]; then
                    echo "    $NAME"
                    echo "        (=$ALIAS)"
                else
                    echo "    $NAME"
                    # COPY THE SUMMARY INTO EACH SUB COMMAND?
                    # ()This is how it is done in rose - so there is no
                    # central file containing all the summaries..)
                    #sed 's/^"""\(.*\)""".*/\1/' a $CYLC_HOME_BIN/$U
                    sed '1,/^# DESCRIPTION$/d;{s/^# /    /;q;}' \
                        $CYLC_HOME_BIN/$U
                fi
            done
        } | ${PAGER:-less}
        exit 0
    fi
    RC=0
    for U in "$@"; do
        if [[ $U == 'help' || $U == 'version' ]]; then
            continue
        fi
        help_util $U || RC=$?
    done
    exit $RC
    :;;
version|--version|-V)
    print_version
    exit
    :;;
esac

#echo $CYLC_NS
#echo $UTIL

COMMAND=$(dirname $0)/$CYLC_NS-$UTIL
if [[ ! -f $COMMAND || ! -x $COMMAND ]]; then
    echo "$CYLC_NS: $UTIL: unknown utility. Abort." >&2
    echo "Type \"$CYLC_NS help\" for a list of utilities." >&2
    exit 1
fi
if (($# > 0)) && [[ $1 == '--help' || $1 == '-h' ]]; then
    help_util $UTIL
    exit
fi

CYLC_UTIL=$UTIL
export CYLC_UTIL

#echo "Command: $COMMAND"
#echo "Args: $@"
exec $COMMAND "$@"
