# Copyright (C) 2020 GrammaTech, Inc.
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


class NoBinaryError(TestError):
    def __init__(self):
        log.error("No binary provided for testing")


class Result(enum.Enum):
    PASS = "pass"
    FAIL = "fail"


class Test():
    def __init__(self, limit_bin, tests_dir, limit=1):
        self.binary = None
        self.limit_bin = limit_bin
        self.tests_dir = tests_dir
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

    def run_limited(self, command, stdin=None):
        limit_command = [self.limit_bin, self.limit] + command
        return sp.run(limit_command, stdin=stdin,
                      stdout=sp.PIPE, stderr=sp.PIPE)

    def test_one(self, test_id):
        raise NotImplementedError

    def run_tests(self, max_tests=None, fail_early=True):
        """Runs tests. Returns a tuple of (num_passed, num_failed)"""
        if self.binary is None:
            raise NoBinaryError
        passed = 0
        failed = 0
        if max_tests is None:
            tests_to_run = self.test_ids
        else:
            tests_to_run = self.test_ids[:max_tests]
        for test_id in tests_to_run:
            result = self.test_one(test_id)
            if result == Result.FAIL:
                log.debug(f"{test_id}: FAIL")
                failed += 1
                if fail_early:
                    break
            else:
                log.debug(f"{test_id}: OK")
                passed += 1
        log.debug(f"Passed: {passed}, Failed: {failed}")
        return (passed, failed)
