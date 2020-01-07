# Copyright (C) 2020 GrammaTech, Inc.
from datetime import datetime
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

    def item_str(self, item):
        return str(item)

    def search(self):
        raise NotImplementedError

    def run(self):
        self.start_time = datetime.now()
        results = self.search()
        self.finish_time = datetime.now()
        log.info(f"Items to delete:\n{' '.join(results)}")
        runtime = self.finish_time - self.start_time
        log.info(f"Runtime: {runtime}")
        log.info("Building and testing final configuration")
        self._test(results)
        return results


class Linear(Simple):
    def search(self):
        to_delete = list()
        for item in self.deleter.items:
            log.info(f"Trying {self.item_str(item)}")
            result = self._test(to_delete + [item])
            if result == Result.PASS:
                to_delete.append(item)
        return to_delete


class Bisect(Simple):
    def search(self):
        to_delete = self.deleter.items

        def search(items):
            log.info(f"Trying {' '.join(self.item_str(x) for x in items)}")
            if items == []:
                return items
            result = self._test(items)
            if result == Result.PASS:
                return items
            if len(items) == 1:
                return []
            midpoint = len(items)//2
            subset =  search(items[:midpoint]) + search(items[midpoint:])
            if len(subset) > 1:
                subset_str = ' '.join(self.item_str(x) for x in subset)
                log.info(f"Trying combined results {subset_str}")
                if self._test(subset) == Result.FAIL:
                    log.error(f"Subset expected to pass {subset_str}")
            return subset
        return search(to_delete)

    def run(self):
        self.start_time = datetime.now()
        results = self.search()
        self.finish_time = datetime.now()
        log.info("Items to delete:\n"
                 f"{' '.join(self.item_str(x) for x in results)}")
        runtime = self.finish_time - self.start_time
        log.info(f"Runtime: {runtime}")
        return results
