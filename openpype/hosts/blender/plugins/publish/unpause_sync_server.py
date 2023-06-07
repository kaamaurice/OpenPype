from concurrent.futures import as_completed
import re
import subprocess

import pyblish
from openpype.hosts.blender.api.utils import ERROR_MAGIC

from openpype.modules.base import ModulesManager
from openpype.modules.timers_manager.plugins.publish.start_timer import (
    StartTimer,
)

BUILTIN_EXCEPTIONS={"BaseException",
"GeneratorExit",
"KeyboardInterrupt",
"SystemExit",
"Exception",
"ArithmeticError",
"FloatingPointError",
"OverflowError",
"ZeroDivisionError",
"AssertionError",
"AttributeError",
"BufferError",
"EOFError",
"ImportError",
"ModuleNotFoundError",
"LookupError",
"IndexError",
"KeyError",
"MemoryError",
"NameError",
"UnboundLocalError",
"OSError",
"BlockingIOError",
"ChildProcessError",
"ConnectionError",
"BrokenPipeError",
"ConnectionAbortedError",
"ConnectionRefusedError",
"ConnectionResetError",
"FileExistsError",
"FileNotFoundError",
"InterruptedError",
"IsADirectoryError",
"NotADirectoryError",
"PermissionError",
"ProcessLookupError",
"TimeoutError",
"ReferenceError",
"RuntimeError",
"NotImplementedError",
"RecursionError",
"StopAsyncIteration",
"StopIteration",
"SyntaxError",
"IndentationError",
"TabError",
"SystemError",
"TypeError",
"ValueError",
"UnicodeError",
"UnicodeDecodeError",
"UnicodeEncodeError",
"UnicodeTranslateError",
"Warning",
"BytesWarning",
"DeprecationWarning",
"EncodingWarning",
"FutureWarning",
"ImportWarning",
"PendingDeprecationWarning",
"ResourceWarning",
"RuntimeWarning",
"SyntaxWarning",
"UnicodeWarning",
"UserWarning"}

def all_subclasses(cls):
    return set(cls.__subclasses__()).union(
        [s for c in cls.__subclasses__() for s in all_subclasses(c)])

class UnpauseSyncServer(pyblish.api.ContextPlugin):
    label = "Unpause Sync Server"
    hosts = ["blender"]
    order = StartTimer.order

    def process(self, context):
        manager = ModulesManager()
        sync_server_module = manager.modules_by_name["sync_server"]
        sync_server_module.unpause_server()


        # all_errors = all_subclasses(BaseException)
        print("tqat", ("|".join(f"{e}: .*" for e in BUILTIN_EXCEPTIONS)))
        match = re.compile("|".join(f"{e}: .*" for e in BUILTIN_EXCEPTIONS))
        
        # Wait for all started futures to finish
        subprocess_errors = False
        for instance in context:
            for future in as_completed(
                instance.data.get("representations_futures", [])
            ):
                
                result = future.result().decode()
                print(future.result())
                print("toto", result)

                if errors_stack := re.finditer(match, result):
                    # print("toto2", errors_stack)
                    for stack in errors_stack:
                        print("toto3", stack)

                        error = stack.group(0).split(":")
                        self.log.error(f"{error[0]}: {error[1].strip()}")
                        # raise eval(error[0])(error[1].strip())
                        # errors = eval(stack.group(1))

                        # for e in errors:
                        #     raise e
                    subprocess_errors = True
                else:
                    self.log.info(result)
        print("toto", subprocess_errors)
        if subprocess_errors:
            raise RuntimeError("Errors happened during subprocesses. See above.")

