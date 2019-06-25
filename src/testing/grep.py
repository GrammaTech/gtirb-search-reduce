import logging as log
import os

from collections import defaultdict

from testing.test import Test, Result


class GrepTest(Test):
    """Testing for the grep-single-file binary.
    Assumes the following layout for a test directory:
        test_dir/[flag]/[test_id]/{input,pattern,returncode,stderr,stdout}
    """
    def __init__(self, binary, limit_bin, tests_dir, flag=None):
        if flag is not None:
            tests_dir = os.path.join(tests_dir, flag)
            flag = '-' + flag
        else:
            tests_dir = os.path.join(tests_dir, 'vanilla')
        self.flag = flag
        super().__init__(binary, limit_bin, tests_dir)
        self.test_ids = self.get_tests_sorted()

    def get_tests_sorted(self):
        """Lists test IDs in increasing order of size of pattern + input."""
        file_info = defaultdict(int)
        with os.scandir(self.tests_dir) as tests:
            for t in tests:
                size = sum((os.stat(os.path.join(t.path, f)).st_size
                            for f in ('input', 'pattern')))
                file_info[t.name] += size
        return [f[0] for f in sorted(file_info.items(), key=lambda f: f[1])]

    def test_one(self, test_id):
        """Runs a single test case"""
        test_dir = os.path.join(self.tests_dir, test_id)
        pattern, stdout, stderr, returncode = \
            (Test.read_file(os.path.join(test_dir, f))
             for f in ('pattern', 'stdout', 'stderr', 'returncode'))

        # Decode and convert returncode to int
        returncode = int(returncode.decode('utf-8').strip())
        command = [self.binary, '-e', pattern]
        if self.flag is not None:
            command.append(self.flag)
        with open(os.path.join(test_dir, 'input'), 'rb') as input_file:
            result = self.run_limited(command, stdin=input_file)

        if (stdout, stderr, returncode) == \
            (result.stdout, result.stderr, result.returncode):
            return Result.PASS
        else:
            return Result.FAIL
