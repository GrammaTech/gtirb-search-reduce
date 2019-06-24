import logging as log
import os

from collections import defaultdict

from test import Test, Result


class GrepTest(Test):
    def __init__(self, binary, limit_bin, test_dir, flag=None):
        super().__init__(binary, limit_bin, test_dir)
        self.flag = flag
        self.test_ids = self.get_tests_sorted()

    def get_tests_sorted(self):
        """Lists test IDs in increasing order of size of pattern + input.
        Assumes that the 'input' directory contains '.pattern' and '.input'
        files of the format [test_id].{pattern,input}"""
        file_info = defaultdict(int)
        with os.scandir(os.path.join(self.test_dir, 'input')) as infiles:
            for f in infiles:
                test_id = f.name.split('.')[0]
                file_info[test_id] += f.stat().st_size
        return [f[0] for f in sorted(file_info.items(), key=lambda f: f[1])]

    def test_one(self, test_id):
        """Runs a single test case"""
        pat_path = os.path.join(self.test_dir, 'input', test_id + '.pattern')
        in_path = os.path.join(self.test_dir, 'input', test_id + '.input')
        pattern, input_str = (str(Test.read_file(x))
                              for x in (pat_path, in_path))
        command = [self.binary, pattern_path]
        if self.flag is not None:
            command.append(self.flag)
        command.append(input_str)
        res = Test.run_limited(command)

        out_path = os.path.join(self.test_dir, 'oracle', test_id + '.stdout')
        err_path = os.path.join(self.test_dir, 'oracle', test_id + '.stderr')
        code_path = os.path.join(self.test_dir, 'oracle', test_id + '.code')
        out, err, code = (Test.read_file(x)
                          for x in (out_path, err_path, code_path))
        if out == res.stdout and err == res.stderr and code == res.returncode:
            log.debug(f"{test_id}: OK")
            return Result.PASS
        else:
            log.debug(f"{test_id}: FAIL")
            return Result.FAIL
