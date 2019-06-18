#!/usr/bin/env python3

import argparse
import copy
import logging as log
import tempfile
import shutil
import subprocess
import sys
import os
from gtirb import *

import block_deleter
from search.DD import DD, Result


class PersistentTemporaryDirectory(tempfile.TemporaryDirectory):
    """Uses tempfile's TemporaryDirectory, but adds the ability to save the
    directory when used as a context manager."""

    def __init__(self, suffix=None, prefix=None, dir=None, save_dir=None):
        self.save_dir = save_dir
        super().__init__(suffix, prefix, dir)

    def __exit__(self, exc, value, tb):
        if self.save_dir is not None:
            try:
                shutil.copytree(src=self.name, dst=self.save_dir)
            except OSError as e:
                log.error("Error copying "
                          f"{self.name} to {self.save_dir}:\n"
                          f"{e}")
        super().__exit__(exc, value, tb)


class DDBlocks(DD):
    def __init__(self, infile, trampoline, workdir, save_files):
        DD.__init__(self)
        self.infile = infile
        self.trampoline = trampoline
        self.workdir = workdir
        self.save_files = save_files
        self._read_ir()
        self.blocklist = block_deleter.block_addresses(self._ir)
        self.test_count = 0

    def _read_ir(self):
        if not os.path.exists(self.infile):
            sys.exit(f"Error: Input file {infile} does not exist.")
        self._ir_loader = IRLoader()
        self._ir = self._ir_loader.IRLoadFromProtobufFileName(self.infile)
        self._factory = self._ir_loader._factory

    def _test(self, blocks):
        blocks = set(blocks)
        delete_blocks = [x for x in self.blocklist if x not in blocks]
        delete_blocks_list = ' '.join([str(b) for b in delete_blocks])
        self.test_count += 1
        log.info(f"Test #{self.test_count}")
        log.debug(f"Processing: \n{delete_blocks_list}")

        # Re-read IR every time
        log.info("Reading IR")
        self._read_ir()
        # Generate new IR
        log.info("Deleting blocks")
        block_deleter.remove_blocks(self._ir, self._factory,
                                    block_addresses=delete_blocks)
        # Output to a GTIRB file
        save_dir = None
        if self.save_files == 'all':
            save_dir = os.path.join(self.workdir, str(self.test_count))
        with PersistentTemporaryDirectory(prefix=str(self.test_count) + '-',
                                          dir=self.workdir,
                                          save_dir=save_dir) as cur_dir, \
             open(os.path.join(cur_dir, 'blocks.txt'), 'w+b') as block_list, \
             open(os.path.join(cur_dir, 'out.ir'), 'w+b') as ir_file:
            asm = os.path.join(cur_dir, 'out.S')
            exe = os.path.join(cur_dir, 'out.exe')
            block_list.write(delete_blocks_list.encode())
            ir_file.write(self._ir.toProtobuf().SerializeToString())
            ir_file.flush()
            # Dump assembly
            log.info("Dumping assembly")
            pprinter_command = ['gtirb-pprinter',
                                '-i', ir_file.name,
                                '-o', asm]
            try:
                result = subprocess.run(pprinter_command,
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL)
                if result.returncode != 0:
                    log.error(f"gtirb-pprinter failed to assemble {asm}")
                    log.info("FAIL")
                    return Result.PASS
            except Exception:
                log.error("Exception while running gtirb-pprinter")
                log.info("FAIL")
                return Result.PASS

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
                    log.info("FAIL")
                    return Result.PASS
            except Exception:
                log.error("exception while running gcc")
                log.info("FAIL")
                return Result.PASS

            # Run tests
            log.info("Testing")
            test_command = ['tests/test.py', exe]
            result = subprocess.run(test_command)
            if result.returncode == 0:
                log.info("PASS")
                log.debug("Blocks deleted:\n"
                          f"{' '.join([str(b) for b in delete_blocks])}")
                if self.save_files == 'passing':
                    save_dir = os.path.join(self.workdir, str(self.test_count))
                    try:
                        shutil.copytree(src=cur_dir, dst=save_dir)
                    except OSError as e:
                        log.error("Error copying "
                                  f"{self.name} to {self.save_dir}:\n"
                                  f"{e}")
                return Result.FAIL
            else:
                os.remove(exe)
                log.info("FAIL")
                return Result.PASS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--in",
                        help="input GTIRB file",
                        metavar="FILE",
                        dest='in_file',
                        required=True)
    parser.add_argument("-o", "--out",
                        help="output GTIRB file",
                        metavar="FILE",
                        default='out.ir')
    parser.add_argument("-t", "--tramp",
                        help="trampoline file",
                        metavar="FILE",
                        action='store',
                        default='etc/__gtirb_trampoline.S')
    parser.add_argument("--log-file",
                        help="log file")
    parser.add_argument("--log-level",
                        help="log level",
                        metavar="LEVEL",
                        choices=[log.getLevelName(l) for l in
                                 [log.ERROR, log.INFO, log.DEBUG]],
                        default=log.INFO)
    parser.add_argument("-w", "--workdir",
                        help="working directory",
                        metavar="DIR",
                        default=None)
    parser.add_argument("-s", "--save",
                        help="save files generated during the search",
                        choices=['all', 'passing'])

    args = parser.parse_args()
    if not os.path.exists(args.in_file):
        sys.exit(f"Error: Input file {args.in_file} does not exist.")
    if not os.path.exists(args.tramp):
        sys.exit(f"Error: Trampoline file {args.tramp} does not exist")

    format = '[%(levelname)-5s %(asctime)s] - %(module)s: %(message)s'
    datefmt = '%m/%d %H:%M:%S'
    if args.log_file:
        log.basicConfig(filename=args.log_file, format=format,
                        datefmt=datefmt, level=args.log_level)
    else:
        log.basicConfig(level=args.log_level, format=format, datefmt=datefmt)

    dd = DDBlocks(infile=args.in_file,
                  trampoline=args.tramp,
                  workdir=args.workdir,
                  save_files=args.save)
    blocks = set(dd.ddmin(dd.blocklist))
    deleted_blocks = [b for b in dd.blocklist if b not in blocks]

    ir_loader = IRLoader()
    ir = ir_loader.IRLoadFromProtobufFileName(args.in_file)
    factory = ir_loader._factory
    block_deleter.remove_blocks(ir, factory, block_addresses=deleted_blocks)
    ir_out = ir.toProtobuf()

    log.info(f"Blocks to delete:\n"
             f"{' '.join([str(b) for b in deleted_blocks])}")
    with open(args.out, 'wb') as outfile:
        outfile.write(ir_out.SerializeToString())


if __name__ == '__main__':
    main()
