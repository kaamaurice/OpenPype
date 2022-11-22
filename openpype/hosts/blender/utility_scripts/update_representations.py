import argparse
import sys

import bpy
from openpype.client.entities import (
    get_asset_by_name,
    get_representation_by_id,
    get_subset_by_name,
)
from openpype.hosts.blender.api.pipeline import metadata_update
from openpype.pipeline import legacy_io
from openpype.pipeline.constants import AVALON_CONTAINER_ID

if __name__ == "__main__":
    # Parse arguments
    parser = argparse.ArgumentParser(
        description="Update AVALON metadata with given representation ID."
    )
    parser.add_argument(
        "subset_name",
        type=str,
        nargs="?",
        help="subset name",
    )
    parser.add_argument(
        "--datablocks",
        type=str,
        nargs="*",
        help="list of datablocks names to add container metadata to",
        required=True,
    )
    parser.add_argument(
        "--datapaths",
        type=str,
        nargs="*",
        help="list of datapaths to get datablocks from",
        required=True,
        # TODO set default with outliner types
    )
    parser.add_argument(
        "--id",
        dest="representation_id",
        type=str,
        nargs="?",
        help="representation ID",
        required=True,
    )
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])

    for datapath in args.datapaths:
        for datablock_name in args.datablocks:
            datablock = eval(datapath).get(datablock_name)

            # Get docs
            project_name = legacy_io.Session["AVALON_PROJECT"]
            asset_name = legacy_io.Session["AVALON_ASSET"]

            asset_doc = get_asset_by_name(project_name, asset_name)
            subset_doc = get_subset_by_name(
                project_name, args.subset_name, asset_doc["_id"]
            )
            representation_doc = get_representation_by_id(
                project_name, args.representation_id
            )

            # Update container metadata
            metadata_update(
                datablock,
                {
                    "schema": "openpype:container-2.0",
                    "id": AVALON_CONTAINER_ID,
                    "name": args.subset_name,
                    "representation": args.representation_id,
                    "asset_name": legacy_io.Session["AVALON_ASSET"],
                    "parent": str(asset_doc["parent"]),
                    "family": representation_doc.data["family"],
                    "namespace": "",
                },
            )

    bpy.ops.wm.save_mainfile()
