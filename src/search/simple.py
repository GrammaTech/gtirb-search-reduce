import logging as log
import os
import shutil

from gtirb import *

from gtirbtools.deleter import BlockDeleter, FunctionDeleter, IRGenerationError


class Result(Enum):
    PASS = 'pass'
    FAIL = 'fail'


class Simple():
    """Base class for simple search approaches."""

    def __init__(self, save_files, tester, deleter):
        self.save_files = save_files
        self.tester = tester
        self.deleter = deleter
        self.test_count = 0

    def _test(self, items):
        def finish_test(test_dir, result):
            def copy_dir(dst):
                try:
                    shutil.copytree(src=test_dir, dst=dst)
                except OSError as e:
                    log.error(f"Error copying {test_dir} to {dst}:\n{e}")
            save_dir = os.path.join(self.deleter.workdir,
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
            test_dir = self.deleter.delete(items, str(self.test_count) + '-')
        except IRGenerationError as e:
            return finish_test(e.dir_name, Result.FAIL)

        exe = os.path.join(test_dir.name, self.deleter.binary_name)
        self.tester.binary = exe

        # Run tests
        log.info("Starting tests")
        passed, failed = self.tester.run_tests()
        if failed != 0:
            return finish_test(test_dir.name, Result.FAIL)
        else:
            log.debug("Deleted:\n"
                      f"{items_list}")
            new_size = os.stat(exe).st_size
            finish_test(test_dir.name, Result.PASS)
            log.info(f"New file size: {new_size} bytes, "
                     f"{new_size / self.deleter.original_size * 100:.2f}% "
                     "of original size")
            return Result.PASS

    def run(self):
        raise NotImplementedError


class Linear(Simple):
    def run(self):
        to_delete = list()
        for item in self.deleter.items:
            result = self._test(to_delete + [item])
            if result == Result.PASS:
                to_delete.append(item)
        return to_delete


class LinearBlocks(Linear):
    def __init__(self, infile, trampoline, workdir, save_files, tester):
        deleter = BlockDeleter(infile, trampoline, workdir)
    def __init__(self, infile, trampoline, workdir,
                 save_files, tester, binary_name='out.exe'):
        deleter = BlockDeleter(infile, trampoline, workdir, binary_name)
        super().__init__(save_files, tester, deleter)


class LinearFunctions(Linear):
    def __init__(self, infile, trampoline, workdir,
                 save_files, tester, binary_name='out.exe'):
        deleter = FunctionDeleter(infile, trampoline, workdir, binary_name)
        super().__init__(save_files, tester, deleter)


class Bisect(Simple):
    def run(self):
        to_delete = self.deleter.items

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
    def item_str(self, block):
        return f'0x{block:x}'

    def __init__(self, infile, trampoline, workdir,
                 save_files, tester, binary_name='out.exe'):
        deleter = BlockDeleter(infile, trampoline, workdir, binary_name)
        super().__init__(save_files, tester, deleter)


class BisectFunctions(Bisect):
    def __init__(self, infile, trampoline, workdir,
                 save_files, tester, binary_name='out.exe'):
        deleter = FunctionDeleter(infile, trampoline, workdir, binary_name)
        super().__init__(save_files, tester, deleter)
