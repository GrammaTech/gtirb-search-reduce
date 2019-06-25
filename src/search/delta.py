import logging as log
import os

from gtirb import *

from gtirbtools.Deleter import Deleter, IRGenerationError
from search.DD import DD, Result
from testing.test import Test


class Delta(DD, Deleter):
    """Base class for delta debugging approaches.
    Must override the _delete() method in a subclass"""

    def __init__(self, infile, trampoline, workdir, save_files, tester):
        DD.__init__(self)
        Deleter.__init__(self, infile=infile,
                         trampoline=trampoline, workdir=workdir)
        self.save_files = save_files
        self.tester = tester
        self.test_count = 0

    def _finish_test(self, test_result, dir_name):
        """Saves the test directory depending on the result"""
        def copy_dir(dst):
            try:
                shutil.copytree(src=cur_dir, dst=dst)
            except OSError as e:
                log.error("Error copying "
                          f"{cur_dir} to {dst}:\n"
                          f"{e}")
        result = {Result.FAIL: 'pass',
                  Result.PASS: 'fail'}[test_result]
        save_dir = os.path.join(self.workdir,
                                result,
                                str(self.test_count))
        if self.save_files == 'all':
            copy_dir(save_dir)
        elif self.save_files == 'passing' and result == 'fail':
            copy_dir(save_dir)
        log.info(result.upper())
        return test_result

    def _test(self, items):
        """NOTE: Result.PASS and Result.FAIL have counterintuitive meanings
        here because of the assumptions of Delta Debugging"""
        items = set(items)
        delete_items = [x for x in self.items if x not in items]
        delete_items_list = ' '.join(sorted([str(b) for b in delete_items]))
        self.test_count += 1
        log.info(f"Test #{self.test_count}")
        log.debug(f"Processing: \n{delete_items_list}")

        try:
            test_dir = \
                self.delete(ir, delete_items, str(self.test_count) + '-')
        except IRGenerationError as e:
            return self._finish_test(Result.PASS, e.dir_name)

        exe = os.path.join(test_dir, 'out.exe')
        self.tester.binary = exe

        # Run tests
        log.info("Testing")
        passed, failed = self.tester.run_tests()
        if failed != 0:
            return self._finish_test(Result.PASS, test_dir)
        else:
            log.debug("Deleted:\n"
                      f"{delete_items_list}")
            new_size = os.stat(exe).st_size
            self._finish_test(Result.FAIL, test_dir)
            log.info(f"New file size: {new_size} bytes, "
                     f"{new_size / self.original_size * 100:.2f}% "
                     "of original size")
            return Result.FAIL

    def _delete(self, items):
        raise NotImplementedError


class DeltaBlocks(Delta):
    def __init__(self, infile, trampoline, workdir, save_files, tester):
        super().__init__(infile, trampoline, workdir, save_files, tester)
        self.blocks = list(block_deleter.block_addresses(self._ir))
        self.items = self.blocks

    def _delete(self, ir, factory, blocks):
        log.info("Deleting blocks")
        block_deleter.remove_blocks(ir, factory, blocks)


class DeltaFunctions(Delta):
    def __init__(self, infile, trampoline, workdir, save_files, tester):
        super().__init__(infile, trampoline, workdir, save_files, tester)
        self.functions = list(block_deleter.get_function_map(self._ir).keys())
        self.items = self.functions

    def _delete(self, ir, factory, functions):
        log.info("Deleting functions")
        block_deleter.remove_functions(ir, factory, functions)
