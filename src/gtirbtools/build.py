import logging as log
import os
import tempfile
import subprocess

from gtirb import *


class BuildError(Exception):
    """Base class for exceptions in this module."""
    pass


class AssemblerError(BuildError):
    """Exception raised for errors during assembly."""
    def __init__(self, message):
        self.message = message


class CompilerError(BuildError):
    """Exception raised for errors during compilation."""
    def __init__(self, message):
        self.message = message


def build(ir, trampoline, build_dir, binary_name, build_flags):
    """Creates out.{ir,S,exe} in build_dir"""
    with open(os.path.join(build_dir, binary_name + '.ir'), 'w+b') as ir_file:
        asm = os.path.join(build_dir, binary_name + '.S')
        exe = os.path.join(build_dir, binary_name)

        log.info("Serializing IR")
        ir_file.write(ir.toProtobuf().SerializeToString())
        ir_file.flush()

        # Generate assembly
        log.info("Generating assembly")
        pprinter_command = ['gtirb-pprinter',
                            '-i', ir_file.name,
                            '-o', asm]
        try:
            res = subprocess.run(pprinter_command,
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            if res.returncode != 0:
                raise AssemblerError(f"Failed to assemble {asm}")
        except subprocess.SubprocessError:
            raise AssemblerError(f"Caught exception")

        # Compile
        build_command = ['gcc', '-no-pie',
                         asm, trampoline]
        build_command += build_flags
        build_command += ['-o', exe]
        try:
            res = subprocess.run(build_command,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            if res.returncode != 0:
                raise CompilerError(f"Failed to build with error:\n"
                                    f"{res.stderr.decode('utf-8').strip()}")
        except subprocess.SubprocessError:
            raise CompilerError("Exception while running gcc")
