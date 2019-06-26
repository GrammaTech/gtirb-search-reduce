import logging as log
import os

from gtirb import *

from gtirbtools.Deleter import BlockDeleter, FunctionDeleter, IRGenerationError


class Result(Enum):
    PASS = 'pass'
    FAIL = 'fail'


class Simple():
    """Base class for simple search approaches."""

    def __init__(self, save_files, tester, deleter):
        self.save_files = save_files
        self.tester = tester
        self.test_count = 0

    def _test(self, items, fast=False):
        def finish_test(result):
            def copy_dir(dst):
                try:
                    shutil.copytree(src=cur_dir, dst=dst)
                except OSError as e:
                    log.error("Error copying "
                              f"{cur_dir} to {dst}:\n"
                              f"{e}")
            save_dir = os.path.join(self.workdir,
                                    result.value,
                                    str(self.test_count))
            if self.save_files == 'all':
                copy_dir(save_dir)
            elif self.save_files == 'passing' and result == Result.PASS:
                copy_dir(save_dir)
            log.info(result.value.upper())
            return result

        items_list = ' '.join(sorted([str(b) for b in items]))
        self.test_count += 1
        log.info(f"Test #{self.test_count}")
        log.debug(f"Processing: \n{items_list}")

        try:
            test_dir = deleter.delete(ir, items, str(self.test_count) + '-')
        except IRGenerationError as e:
            return finish_test(Result.FAIL, e.dir_name)

        exe = os.path.join(cur_dir, 'out.exe')
        self.tester.binary = exe

        # Run tests
        log.info("Testing")
        passed, failed = self.tester.run_tests()
        if failed != 0:
            return finish_test(Result.FAIL)
        else:
            log.debug("Deleted:\n"
                      f"{items_list}")
            new_size = os.stat(exe).st_size
            finish_test(Result.PASS)
            if not fast:
                log.info(f"New file size: {new_size} bytes, "
                         f"{new_size / self.original_size * 100:.2f}% "
                         "of original size")
            return Result.PASS

    def run(self):
        raise NotImplementedError


class Linear(Simple):
    def run(self):
        to_delete = list()
        for item in self.items:
            result = self._test(to_delete + [item])
            if result == Result.PASS:
                to_delete.append(item)
        return to_delete


class LinearBlocks(Linear):
    def __init__(self, infile, trampoline, workdir, save_files, tester):
        deleter = BlockDeleter(infile, trampoline, workdir)
        super().__init__(save_files, tester, deleter)


class LinearFunctions(Linear):
    def __init__(self, infile, trampoline, workdir, save_files, tester):
        deleter = FunctionDeleter(infile, trampoline, workdir)
        super().__init__(save_files, tester, deleter)


class Bisect(Simple):
    def run(self):
        to_delete = self.items

        def search(items):
            if items == []:
                return items
            result = self._test(items)
            if result == Result.PASS:
                return items
            midpoint = len(items)//2
            return search(items[:midpoint]) + search(items[midpoint:])
        return search(to_delete)


class BisectBlocks(Bisect):
    def __init__(self, infile, trampoline, workdir, save_files, tester):
        deleter = BlockDeleter(infile, trampoline, workdir)
        super().__init__(save_files, tester, deleter)


class BisectFunctions(Bisect):
    def __init__(self, infile, trampoline, workdir, save_files, tester):
        deleter = FunctionDeleter(infile, trampoline, workdir)
        super().__init__(save_files, tester, deleter)
