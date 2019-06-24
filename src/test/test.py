import enum
import logging as log
import os
import subprocess as sp


class TestError(Exception):
    """Base class for testing exceptions"""
    pass


class ReadError(TestError):
    def __init__(self, message):
        self.message = message


class LimitBinaryError(TestError):
    def __init__(self):
        log.error("Could not run 'limit', have you compiled it?")


class Result(enum.Enum):
    PASS = "pass"
    FAIL = "fail"


class Test():
    def __init__(self, binary, limit_bin, test_dir, limit=1):
        self.binary = binary
        self.limit_bin = limit_bin
        self.test_dir = test_dir
        self.limit = str(limit)
        self.test_ids = None
        # Check limit binary
        try:
            sp.run([limit_bin], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        except Exception:
            raise LimitBinaryError

    @staticmethod
    def read_file(file_path):
        contents = None
        with open(file_path, 'rb') as file:
            contents = file.read()
        if contents is None:
            raise ReadError(f"Could not read file {path}")
        return contents

    @staticmethod
    def run_limited(command):
        limit_command = [self.limit_bin, self.limit] + command
        return sp.run(limit_command, stdout=sp.PIPE, stderr=sp.PIPE)

    def test_one(self, test_id):
        raise NotImplementedError

    def run_tests(self, max_tests=None, fail_early=True):
        """Runs tests. Returns a tuple of (num_passed, num_failed)"""
        passed = 0
        failed = 0
        if max_tests is None:
            tests_to_run = self.test_ids
        else:
            tests_to_run = self.test_ids[:max_tests]
        for test_id in tests_to_run:
            result = self.test_one(test_id)
            if result == Result.FAIL:
                failed += 1
                if fail_early:
                    break
            else:
                passed += 1
        return (passed, failed)
