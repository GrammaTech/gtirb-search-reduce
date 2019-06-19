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
from search.DD import DD, Result


class DDDeleter(DD):
    """Base class for delta debugging approaches.
    Must override the _delete() method in a subclass"""

    def __init__(self, infile, trampoline, workdir, save_files):
        DD.__init__(self)
        self.infile = infile
        self.trampoline = trampoline
        self.workdir = workdir
        self.save_files = save_files
        self._read_ir()
        self.original_size = self._get_original_file_size()
        if self.original_size is None:
            sys.exit(f"Error: Could not build original file")
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
            return os.stat(exe).st_size

    def _test(self, items):
        items = set(items)
        delete_items = [x for x in self.items if x not in items]
        delete_items_list = ' '.join(sorted([str(b) for b in delete_items]))
        self.test_count += 1
        log.info(f"Test #{self.test_count}")
        log.debug(f"Processing: \n{delete_items_list}")

        # I (Jeremy) profiled pickle.loads(pickle.dumps()) and copy.deepcopy()
        # and found that the pickle/unpickle method is about 5x faster. I think
        # this is because deepcopy() has a lot of bookkeeping for corner cases.
        log.info("Copying IR")
        ir = pickle.loads(pickle.dumps(self._ir))

        # Generate new IR
        self._delete(ir, self._factory, delete_items)

        # Output to a GTIRB file
        with tempfile.TemporaryDirectory(prefix=str(self.test_count) + '-',
                                         dir=self.workdir) as cur_dir, \
             open(os.path.join(cur_dir, 'deleted.txt'), 'w+') as item_list:

            # Save if needed
            def finish_test(test_result):
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

            item_list.write(delete_items_list + "\n")
            item_list.flush()

            try:
                build_ir.build(ir, self.trampoline, cur_dir)
            except build_ir.BuildError as e:
                log.info(e.message)
                return finish_test(Result.PASS)
            exe = os.path.join(cur_dir, 'out.exe')

            # Run tests
            log.info("Testing")
            test_command = ['tests/test.py', exe]
            res = subprocess.run(test_command)
            if res.returncode != 0:
                return finish_test(Result.PASS)
            else:
                log.debug("Deleted:\n"
                          f"{delete_items_list}")
                new_size = os.stat(exe).st_size
                finish_test(Result.FAIL)
                log.info(f"New file size: {new_size}, "
                         f"{new_size / self.original_size * 100:.2f}% "
                         "of original size")
                return Result.FAIL

    def _delete(self, items):
        raise NotImplementedError


class DDBlocks(DDDeleter):
    def __init__(self, infile, trampoline, workdir, save_files):
        super().__init__(infile, trampoline, workdir, save_files)
        self.blocks = list(block_deleter.block_addresses(self._ir))
        self.items = self.blocks

    def _delete(self, ir, factory, blocks):
        log.info("Deleting blocks")
        block_deleter.remove_blocks(ir, factory, blocks)


class DDFunctions(DDDeleter):
    def __init__(self, infile, trampoline, workdir, save_files):
        super().__init__(infile, trampoline, workdir, save_files)
        self.functions = list(block_deleter.get_function_map(self._ir).keys())
        self.items = self.functions

    def _delete(self, ir, factory, functions):
        log.info("Deleting functions")
        block_deleter.remove_functions(ir, factory, functions)
