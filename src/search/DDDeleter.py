import logging as log
import pickle
import tempfile
import shutil
import subprocess
import sys
import os

from gtirb import *

import block_deleter
from search.DD import DD, Result


class DDDeleter(DD):
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
        with tempfile.NamedTemporaryFile(suffix='ir') as ir_file, \
             tempfile.NamedTemporaryFile(suffix='.S') as asm, \
             tempfile.NamedTemporaryFile(suffix='exe') as exe:
            ir_file.write(self._ir.toProtobuf().SerializeToString())
            ir_file.flush()
            # Dump assembly
            pprinter_command = ['gtirb-pprinter',
                                '-i', ir_file.name,
                                '-o', asm.name]
            try:
                res = subprocess.run(pprinter_command,
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                if res.returncode != 0:
                    log.error(f"gtirb-pprinter failed to assemble {asm}")
                    return None
            except Exception:
                log.error("Exception while running gtirb-pprinter")
                return None

            # Compile
            build_command = ['gcc', '-no-pie',
                             asm.name, self.trampoline,
                             '-o', exe.name]
            try:
                res = subprocess.run(build_command,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
                if res.returncode != 0:
                    log.error(f"gcc failed to build with error:\n"
                              f"{res.stderr.decode('utf-8').strip()}")
                    return None
            except Exception:
                log.error("Exception while running gcc")
                return None

            # Get file size
            return os.stat(exe.name).st_size

    def _test(self, items):
        items = set(items)
        delete_items = [x for x in self.items if x not in items]
        delete_items_list = ' '.join(sorted([str(b) for b in delete_items]))
        self.test_count += 1
        log.info(f"Test #{self.test_count}")
        log.debug(f"Processing: \n{delete_items_list}")

        # Copy IR

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
             open(os.path.join(cur_dir, 'deleted.txt'), 'w+') as item_list, \
             open(os.path.join(cur_dir, 'out.ir'), 'w+b') as ir_file:

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

            asm = os.path.join(cur_dir, 'out.S')
            exe = os.path.join(cur_dir, 'out.exe')
            item_list.write(delete_items_list + "\n")
            item_list.flush()
            ir_file.write(ir.toProtobuf().SerializeToString())
            ir_file.flush()
            # Dump assembly
            log.info("Dumping assembly")
            pprinter_command = ['gtirb-pprinter',
                                '-i', ir_file.name,
                                '-o', asm]
            try:
                res = subprocess.run(pprinter_command,
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                if res.returncode != 0:
                    log.error(f"gtirb-pprinter failed to assemble {asm}")
                    return finish_test(Result.PASS)
            except Exception:
                log.error("Exception while running gtirb-pprinter")
                return finish_test(Result.PASS)

            # Compile
            log.info("Compiling")
            build_command = ['gcc', '-no-pie',
                             asm, self.trampoline,
                             '-o', exe]
            try:
                res = subprocess.run(build_command,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
                if res.returncode != 0:
                    log.info(f"gcc failed to build with error:\n"
                             f"{res.stderr.decode('utf-8').strip()}")
                    return finish_test(Result.PASS)
            except Exception:
                log.error("exception while running gcc")
                return finish_test(Result.PASS)

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
