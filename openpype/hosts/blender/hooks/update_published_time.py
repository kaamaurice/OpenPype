from openpype.client.entities import get_last_version_by_subset_id, get_matching_subset_id, get_representation_by_task

from openpype.lib import PreLaunchHook


class AddUpdatePublishedTimeToLaunchArgs(PreLaunchHook):
    """Run `file.make_paths_absolute` operator before open."""

    # Append after file argument
    order = 10
    app_groups = [
        "blender",
    ]

    def execute(self):
        if not self.data.get("source_filepath"):
            return

        # TODO Used only for conformation for old files downloaded with download last published workfile
        # Get data
        project_name = self.data["project_name"]
        asset_name = self.data["asset_name"]
        task_name = self.data["task_name"]

        self.log.info("Update last published time...")

        asset_doc = self.data.get("asset_doc")

        # Get subset ID
        subset_id = get_matching_subset_id(
            project_name, task_name, "workfile", asset_doc
        )
        if subset_id is None:
            self.log.debug(
                "Not any matched subset for task '{}' of '{}'.".format(
                    task_name, asset_name
                )
            )
            return

        # Get workfile representation
        last_version_doc = get_last_version_by_subset_id(
            project_name, subset_id, fields=["data"]
        )
        if not last_version_doc:
            self.log.debug("Subset does not have any versions")
            return
        
        update_puplished_time_line = f"import bpy;bpy.context.scene['op_published_time']='{last_version_doc['data']['time']}'"
        self.launch_context.launch_args.extend(
            [
                "--python-expr",
                update_puplished_time_line,
            ]
        )
