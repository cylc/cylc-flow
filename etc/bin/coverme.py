"""Quick script for wrapping shell calls with python for coverage purposes."""
import subprocess
import sys


def main():
    sys.exit(
        subprocess.call(  # nosec
            sys.argv[1:],
            stdin=subprocess.DEVNULL
        )
    )


if __name__ == '__main__':
    main()
