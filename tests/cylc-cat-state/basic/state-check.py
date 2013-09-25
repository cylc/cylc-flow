import os
import sqlite3
import subprocess
import sys


def main(argv):

    print argv
    if len(argv) != 2:
        print >> sys.stderr, "Incorrect number of args"
        sys.exit(1)

    sname = argv[0]
    rundir = argv[1]

    p = subprocess.Popen("cylc cat-state " + sname, shell=True, 
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    state, err = p.communicate()

    if p.returncode > 0:
        print >> sys.stderr, err
        sys.exit(1)

    db = (os.sep).join([rundir, sname, "cylc-suite.db"])
    cnx = sqlite3.Connection(db)
    cur = cnx.cursor()

    state = state.split("\n")
    states_begun = False

    qbase = "select status from task_states where name==? and cycle==?"

    error_states = []

    for line in state:
        if states_begun and line is not '':
            line2 = line.split(':')
            task_and_cycle = line2[0].strip().split(".")
            status = line2[1].split(',')[0].strip().split("=")[1]
            # query db and compare result
            res = []
            try:
                cur.execute(qbase, [task_and_cycle[0], task_and_cycle[1]])
                next = cur.fetchmany()
                while next:
                    res.append(next[0])
                    next = cur.fetchmany()
            except:
                sys.stderr.write("unable to query suite database\n")
                sys.exit(1)
            if not res[0][0] == status:
                error_states.append(line + ": state retrieved " + str(res[0][0]))
        elif line == "Begin task states":
            states_begun = True

    cnx.close()

    if error_states:
        print >> sys.stderr, "The following task states were not consistent with the database:"
        for line in error_states:
            print >> sys.stderr, line
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
   main(sys.argv[1:])
