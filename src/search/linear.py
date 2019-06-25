from enum import Enum, auto
import logging as log
import pickle
import tempfile
import shutil
import subprocess
import sys
import os

from gtirb import *

import gtirbtools.block_deleter as block_deleter
import gtirbtools.build_ir as build_ir


class Result(Enum):
    PASS = 'pass'
    FAIL = 'fail'


class LinearDeleter():
    """Base class for linear deletion approaches."""

    def __init__(self, infile, trampoline, workdir, save_files, tester):
        self.infile = infile
        self.trampoline = trampoline
        self.workdir = workdir
        self.save_files = save_files
        self._read_ir()
        self.original_size = self._get_original_file_size()
        if self.original_size is None:
            sys.exit(f"Error: Could not build original file")
        self.tester = tester
        self.test_count = 0

    def _read_ir(self):
        if not os.path.exists(self.infile):
            sys.exit(f"Error: Input file {self.infile} does not exist")
        self._ir_loader = IRLoader()
        self._ir = self._ir_loader.IRLoadFromProtobufFileName(self.infile)
        self._factory = self._ir_loader._factory

    def _get_original_file_size(self):
        log.info("Getting original file size")
        with tempfile.TemporaryDirectory() as build_dir:
            build_ir.build(self._ir, self.trampoline, build_dir)
            exe = os.path.join(build_dir, 'out.exe')
            size = os.stat(exe).st_size
            log.info(f"{size} bytes")
            return size

    def _test(self, items, fast=False):
        items_list = ' '.join(sorted([str(b) for b in items]))
        self.test_count += 1
        log.info(f"Test #{self.test_count}")
        log.debug(f"Processing: \n{items_list}")

        # I (Jeremy) profiled pickle.loads(pickle.dumps()) and copy.deepcopy()
        # and found that the pickle/unpickle method is about 5x faster. I think
        # this is because deepcopy() has a lot of bookkeeping for corner cases.
        log.info("Copying IR")
        ir = pickle.loads(pickle.dumps(self._ir))

        # Generate new IR
        self._delete(ir, self._factory, items)

        # Output to a GTIRB file
        with tempfile.TemporaryDirectory(prefix=str(self.test_count) + '-',
                                         dir=self.workdir) as cur_dir, \
             open(os.path.join(cur_dir, 'deleted.txt'), 'w+') as item_list:

            # Save if needed
            def finish_test(result):
                if result == Result.PASS:
                    self.passed += 1
                else:
                    self.failed += 1
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
                log.info(f"Passed: {self.passed}, Failed: {self.failed}")
                return result

            item_list.write(items_list + "\n")
            item_list.flush()

            try:
                build_ir.build(ir, self.trampoline, cur_dir)
            except build_ir.BuildError as e:
                log.info(e.message)
                return finish_test(Result.FAIL)
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

    def _delete(self, items):
        raise NotImplementedError

    def binary_test(self, items, fast=False):
        log.info(f"Trying {items}")
        if len(items) == 0:
            return []
        if self._test(items, fast=fast) == Result.PASS:
            return items
        if len(items) == 1:
            return []
        return self.binary_test(items[len(items)//2:], fast=fast) + \
            self.binary_test(items[:len(items)//2], fast=fast)

    def run(self):
        """Try deleting each item in turn, check if the tests still pass"""
        # fast_delete = set()
        # for num, item in enumerate(self.items):
        #     log.info(f"Quickly trying {num + 1}/{len(self.items)}: '{item}'")
        #     if self._test({item}, fast=True) == Result.PASS:
        #         fast_delete.add(item)
        #     progress = (num + 1)/len(self.items) * 100
        #     log.info(f"{progress:.2f}% complete, "
        #              f"{len(fast_delete)} possible deletions")

        to_delete = self.binary_test(list(self.items))
        log.info(f"Testing final configuration")
        self._test(to_delete)
        return to_delete


class LinearBlocks(LinearDeleter):
    def __init__(self, infile, trampoline, workdir, save_files):
        super().__init__(infile, trampoline, workdir, save_files)
        self.blocks = list(block_deleter.block_addresses(self._ir))
        self.items = self.blocks

    def _delete(self, ir, factory, blocks):
        log.info("Deleting blocks")
        block_deleter.remove_blocks(ir, factory, blocks)


class LinearFunctions(LinearDeleter):
    def __init__(self, infile, trampoline, workdir, save_files):
        super().__init__(infile, trampoline, workdir, save_files)

        # Sort functions by number of basic blocks
        # funmap = block_deleter.get_function_map(self._ir)
        # functions_with_size = list()
        # for f in funmap.keys():
        #     numblocks = len(block_deleter.get_function_block_addresses(f, funmap, self._ir))
        #     functions_with_size.append((f, numblocks))
        # self.functions = [n for n, f in sorted(functions_with_size, key=lambda fun: fun[1])]

        self.functions = list(block_deleter.get_function_map(self._ir).keys())
        self.functions.remove('main')
        self.functions.remove('_start')
        self.items = self.functions

    def _delete(self, ir, factory, functions):
        log.info("Deleting functions")
        block_deleter.remove_functions(ir, factory, functions)
