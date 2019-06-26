from enum import Enum
import logging as log
import os
import shutil

from gtirb import *

import search.DD as DD

from gtirbtools.deleter import BlockDeleter, FunctionDeleter, IRGenerationError


class Result(Enum):
    """Inverts the meaning of pass and fail for compatability
    with Delta Debugging"""
    PASS = DD.Result.FAIL
    FAIL = DD.Result.PASS


class Delta(DD.DD):
    """Base class for delta debugging approaches."""

    def __init__(self, save_files, tester, deleter):
        super().__init__(self)
        self.save_files = save_files
        self.tester = tester
        self.deleter = deleter
        self.test_count = 0

    def _test(self, items):
        def finish_test(self, test_dir, test_result):
            """Saves the test directory depending on the result"""
            def copy_dir(dst):
                try:
                    shutil.copytree(src=test_dir, dst=dst)
                except OSError as e:
                    log.error(f"Error copying {test_dir} to {dst}:\n{e}")
            result = {Result.PASS: 'pass',
                      Result.FAIL: 'fail'}[test_result]
            save_dir = os.path.join(self.deleter.workdir,
                                    result,
                                    str(self.test_count))
            if self.save_files == 'all':
                copy_dir(save_dir)
            elif self.save_files == 'passing' and result == 'fail':
                copy_dir(save_dir)
            log.info(result.upper())
            return test_result

        items = set(self.deleter.items)
        delete_items = [x for x in self.items if x not in items]
        delete_items_list = ' '.join(sorted([str(b) for b in delete_items]))
        self.test_count += 1
        log.info(f"Test #{self.test_count}")
        log.debug(f"Processing: \n{delete_items_list}")

        try:
            test_dir = self.deleter.delete(delete_items,
                                           str(self.test_count) + '-')
        except IRGenerationError as e:
            return finish_test(e.dir_name, Result.FAIL)

        exe = os.path.join(test_dir, 'out.exe')
        self.tester.binary = exe

        # Run tests
        log.info("Testing")
        passed, failed = self.tester.run_tests()
        if failed != 0:
            return finish_test(test_dir.name, Result.FAIL)
        else:
            log.debug("Deleted:\n"
                      f"{delete_items_list}")
            new_size = os.stat(exe).st_size
            finish_test(test_dir.name, Result.PASS)
            log.info(f"New file size: {new_size} bytes, "
                     f"{new_size / self.deleter.original_size * 100:.2f}% "
                     "of original size")
            return Result.PASS

    def run(self):
        return self.ddmin(self.items)


class DeltaBlocks(Delta):
    def __init__(self, infile, trampoline, workdir, save_files, tester):
        deleter = BlockDeleter(infile, trampoline, workdir)
        super().__init__(save_files, tester, deleter)


class DeltaFunctions(Delta):
    def __init__(self, infile, trampoline, workdir, save_files, tester):
        deleter = FunctionDeleter(infile, trampoline, workdir)
        super().__init__(save_files, tester, deleter)
