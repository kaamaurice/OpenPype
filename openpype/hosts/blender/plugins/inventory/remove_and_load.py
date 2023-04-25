from openpype.pipeline import InventoryAction
from openpype.pipeline.legacy_io import Session
from openpype.pipeline.load.plugins import discover_loader_plugins
from openpype.client import (
    get_representation_parents,
    get_representation_by_name,
    get_last_version_by_subset_id,
    get_hero_version_by_subset_id,
)


class RemoveAndLoad(InventoryAction):
    """Delete inventory item and reload it."""

    label = "Delete and load"
    icon = refresh

    def process(self, containers):
        # TODO Create Qt dialog window
        for container in containers:
            project_name = Session.get("AVALON_PROJECT")

            loader_name = container["loader"]
            print(load_name)
            for plugin in discover_loader_plugins(project_name=project_name):
                if get_loader_identifier(plugin) == loader_name:
                    loader = plugin
                    break

            assert (
                loader,
                "Failed to get loader, can't remove and load container",
            )

            current_representation = containers["representation"]
            assert current_representation, "Represenatation not found"

            # get repre by id?

            (
                current_version,
                subset,
                asset,
                project,
            ) = get_representation_parents(
                project_name, current_representation
            )

            assert (
                current_version and subset and asset and project
            ), "Failed to get representation parents"

            loader.remove(
                {
                    "project": {
                        "name": project["name"],
                        "code": project["data"].get("code", ""),
                    },
                    "asset": asset,
                    "subset": subset,
                    "version": current_version,
                    "representation": current_representation,
                }
            )

            # TODO Get is hero
            is_hero = False
            if is_hero:
                new_version = get_hero_version_by_subset_id(
                    project_name, current_version["parent"], fields=["_id"]
                )
            else:
                new_version = get_last_version_by_subset_id(
                    project_name, current_version["parent"], fields=["_id"]
                )

            new_representation = get_representation_by_name(
                project_name,
                current_representation["name"],
                new_version["parent"],
                fields=["_id"],
            )

            loader.update(container, new_representation)
