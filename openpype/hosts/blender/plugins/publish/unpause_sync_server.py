from concurrent.futures import as_completed
import re
import subprocess

import pyblish
from openpype.hosts.blender.api.utils import ERROR_MAGIC

from openpype.modules.base import ModulesManager
from openpype.modules.timers_manager.plugins.publish.start_timer import (
    StartTimer,
)


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


        all_errors = all_subclasses(BaseException)
        print("tqat", ("|".join(f"{e.__name__}: .*" for e in all_errors)))
        match = re.compile("|".join(f"{e.__name__}: .*" for e in all_errors))

        # Wait for all started futures to finish
        for instance in context:
            for future in as_completed(
                instance.data.get("representations_futures", [])
            ):
                try:
                    result = future.result().decode()
                    print("toto", result)

                    if errors_stack := re.finditer(match, result):
                        # print("toto2", errors_stack)
                        for stack in errors_stack:
                            print("toto3", stack)
                            if "Traceback" not in stack.group(1):
                                continue

                            error = stack.group(1).split(":")
                            raise eval(error[0])(error[1].strip())
                            # errors = eval(stack.group(1))

                            # for e in errors:
                            #     raise e
                    else:
                        self.log.info(result)

                except subprocess.CalledProcessError as e:
                    raise RuntimeError(e.stderr.decode("utf-8")) from e
