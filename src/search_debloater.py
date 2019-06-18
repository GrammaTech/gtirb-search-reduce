#!/usr/bin/env python3

import argparse
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


class DDBlocks(DD):
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
        self.blocklist = block_deleter.block_addresses(self._ir)
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

    def _test(self, blocks):
        blocks = set(blocks)
        delete_blocks = [x for x in self.blocklist if x not in blocks]
        delete_blocks_list = ' '.join([str(b) for b in delete_blocks])
        self.test_count += 1
        log.info(f"Test #{self.test_count}")
        log.debug(f"Processing: \n{delete_blocks_list}")

        # Copy IR

        # I (Jeremy) profiled pickle.loads(pickle.dumps()) and copy.deepcopy()
        # and found that the pickle/unpickle method is about 5x faster. I think
        # this is because deepcopy() has a lot of bookkeeping for corner cases.
        log.info("Copying IR")
        ir = pickle.loads(pickle.dumps(self._ir))

        # Generate new IR
        log.info("Deleting blocks")
        block_deleter.remove_blocks(ir, self._factory, block_addresses=delete_blocks)

        # Output to a GTIRB file
        with tempfile.TemporaryDirectory(prefix=str(self.test_count) + '-',
                                         dir=self.workdir) as cur_dir, \
             open(os.path.join(cur_dir, 'blocks.txt'), 'w+b') as block_list, \
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
                result = { Result.FAIL : 'pass',
                           Result.PASS : 'fail' }[test_result]
                save_dir = os.path.join(self.workdir,
                                        'results',
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
            block_list.write(delete_blocks_list.encode())
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
                log.debug("Blocks deleted:\n"
                          f"{' '.join([str(b) for b in delete_blocks])}")
                new_size = os.stat(exe).st_size
                finish_test(Result.FAIL)
                log.info(f"New file size: {new_size}, "
                         f"{new_size / self.original_size * 100}% "
                         "of original size")
                return Result.FAIL


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
    log.basicConfig(level=args.log_level, format=format, datefmt=datefmt)

    if args.log_file:
        fh = log.FileHandler(args.log_file)
        fh.setFormatter(log.Formatter(format))
        log.getLogger().addHandler(fh)

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
