from concurrent.futures import as_completed
import re
import subprocess

import pyblish
from openpype.hosts.blender.api.utils import ERROR_MAGIC

from openpype.modules.base import ModulesManager
from openpype.modules.timers_manager.plugins.publish.start_timer import (
    StartTimer,
)


class UnpauseSyncServer(pyblish.api.ContextPlugin):
    label = "Unpause Sync Server"
    hosts = ["blender"]
    order = StartTimer.order

    def process(self, context):
        manager = ModulesManager()
        sync_server_module = manager.modules_by_name["sync_server"]
        sync_server_module.unpause_server()

        # Wait for all started futures to finish
        for instance in context:
            for future in as_completed(
                instance.data.get("representations_futures", [])
            ):
                try:
                    result = future.result().decode()
                    print("tata", re.findall(f'{ERROR_MAGIC}.*{ERROR_MAGIC}', result, re.MULTILINE), result)

                    if errors_stack := re.findall(f'{ERROR_MAGIC}.*{ERROR_MAGIC}', result, re.MULTILINE):
                        print("patatae", errors_stack.groups())
                        for stack in errors_stack:
                            print(stack)
                            errors = eval(stack)
                            for e in errors:
                                self.log.error(e)
                    else:
                        self.log.info(result)

                except subprocess.CalledProcessError as e:
                    raise RuntimeError(e.stderr.decode("utf-8"))
