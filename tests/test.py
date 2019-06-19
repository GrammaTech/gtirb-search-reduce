#!/usr/bin/env python3

import argparse
import os
import subprocess as sp

# Path to this script
dirname = os.path.dirname(os.path.abspath(__file__))
limit_bin = os.path.join(dirname, 'limit')
verbosity = 0
grep_bin = None


def run_test(test_num, test_dir, input_file, limit):
    inputs_dir = os.path.join(dirname, 'inputs')
    test_input = os.path.join(inputs_dir, input_file)
    test_string = os.path.join(test_dir, 'tests', str(test_num))
    output_path = os.path.join(test_dir, 'outputs', input_file, str(test_num))
    original = None
    with open(output_path, 'rb') as output:
        original = output.read()
    if original is None:
        print(f"Could not read original input for test {test_num}")

    command = [limit_bin, str(limit),
               grep_bin, '-c', '-f', test_string, test_input]
    result = sp.run(command, stdout=sp.PIPE, stderr=sp.PIPE)
    correct = original == result.stdout

    if verbosity > 1:
        if correct:
            print(f"{test_num}: OK")
        else:
            print(f"{test_num}: Failed\n"
                  "Expected:\n"
                  f"{original.decode('utf-8')}\n"
                  "Result:\n"
                  f"{result.stdout.decode('utf-8')}")
    return correct


def finish(passed, failed):
    if verbosity > 1:
        print("-" * 30)
    if verbosity > 0:
        print(f"Passed {passed}, Failed {failed}")
    exit(failed)


def main():
    global verbosity
    global grep_bin
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", help="the binary to test")
    parser.add_argument("-l", "--limit",
                        help="time limit per test in seconds (default=1)",
                        type=int,
                        metavar="L",
                        default=1)
    parser.add_argument("-f", "--full",
                        help="run all tests instead of failing early",
                        action="store_true")
    parser.add_argument("-v", "--verbose",
                        help="verbose output (can be used multiple times)",
                        action="count",
                        default=0)
    # parser.add_argument("-f", "--functionality",
    #                     help="functionality (flags) to test",
    #                     metavar="F",
    #                     nargs="+",
    #                     type=chr)
    # parser.add_argument("-l", "--list",
    #                     help="list testable flags",
    #                     action="store_true")
    args = parser.parse_args()
    verbosity = args.verbose

    # Check for `limit`
    try:
        sp.run([limit_bin], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    except Exception:
        print("Could not run 'limit' have you compiled it?")
        exit(1)

    # Check the test binary
    grep_bin = os.path.abspath(args.binary)
    if not os.path.isfile(grep_bin):
        print(f"Error: file not found {grep_bin}")
        exit(1)
    if not os.access(grep_bin, os.X_OK):
        print(f"Error: permission denied {grep_bin} ")
        exit(1)

    test_dir = os.path.join(dirname, 'flag-c')
    test_strings = os.path.join(test_dir, 'tests')
    passed = 0
    failed = 0
    for test_num in range(len(os.listdir(test_strings))):
        if run_test(test_num=test_num,
                    test_dir=test_dir,
                    input_file="large",
                    limit=args.limit):
            passed += 1
        else:
            failed += 1
            if not args.full:
                finish(passed=passed, failed=failed)
    finish(passed=passed, failed=failed)


if __name__ == "__main__":
    main()
