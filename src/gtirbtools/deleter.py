import logging as log
import pickle
import tempfile
import shutil
import subprocess
import sys
import os

from gtirb import *

import gtirbtools.info as info
from gtirbtools.modify import remove_blocks, remove_functions
from gtirbtools.build import build, BuildError


class DeleterError(Exception):
    """Base class for deleter exceptions"""
    pass


class IRFileNotFound(DeleterError):
    def __init__(self, infile):
        log.error(f"Could not find IR file {infile}")


class IRGenerationError(DeleterError):
    def __init__(self, dir_name):
        log.error(f"Could not generate IR")
        self.dir_name = dir_name


class Deleter():
    """Base class for deletion of code in GTIRB"""
    def __init__(self, infile, trampoline, workdir):
        if not os.path.exists(infile):
            raise IRFileNotFound(infile)
        self.infile = infile
        self.trampoline = trampoline
        self.save_files = save_files
        self._ir_loader = IRLoader()
        self._ir = self._ir_loader.IRLoadFromProtobufFileName(self.infile)
        self._factory = self._ir_loader._factory

    @property
    def original_size(self):
        if self._original_size is None:
            log.info("Getting original file size")
            with tempfile.TemporaryDirectory() as build_dir:
                exe = os.path.join(build_dir, 'out.exe')
                build(self._ir, self.trampoline, build_dir)
                size = os.stat(exe).st_size
            log.info(f"{size} bytes")
            self._original_size = size
        return self._original_size

    def _delete(self, ir, delete_items):
        """Override in subclasses"""
        raise NotImplementedError

    def delete(self, ir, delete_items, name):
        # I (Jeremy) profiled pickle.loads(pickle.dumps()) and copy.deepcopy()
        # and found that the pickle/unpickle method is about 5x faster. I think
        # this is because deepcopy() has a lot of bookkeeping for corner cases.
        log.info("Copying IR")
        ir = pickle.loads(pickle.dumps(self._ir))

        # Generate new IR
        self._delete(ir, self._factory, items)

        # Output to a GTIRB file
        cur_dir = tempfile.TemporaryDirectory(prefix=name, dir=self.workdir)
        with open(os.path.join(cur_dir, 'deleted.txt'), 'w+') as item_list:
            item_list.write(
                ' '.join(sorted([str(i) for i in delete_items])) + "\n"
            )
        try:
            build(ir, self.trampoline, cur_dir)
        except BuildError as e:
            log.info(e.message)
            raise IRGenerationError(cur_dir)
        return cur_dir


class BlockDeleter(Deleter):
    def __init__(self, infile, trampoline, workdir):
        super().__init__(infile, trampoline, workdir)
        self.blocks = info.block_addresses(self._ir)
        self.items = self.blocks

    def _delete(self, ir, blocks):
        log.info("Deleting blocks")
        remove_blocks(ir, self._factory, blocks)


class FunctionDeleter(Deleter):
    def __init__(self, infile, trampoline, workdir):
        super().__init__(infile, trampoline, workdir)
        self.functions = info.get_function_map(self._ir).keys()
        self.items = self.functions

    def _delete(self, ir, functions):
        log.info("Deleting functions")
        remove_functions(ir, self._factory, functions)
