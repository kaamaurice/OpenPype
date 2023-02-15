import copy
import pyblish.api
from openpype.lib import prepare_template_data


class CollectRenderInstances(pyblish.api.InstancePlugin):
    label = "Collect Render Instances"
    order = pyblish.api.CollectorOrder - 0.4
    hosts = ["tvpaint"]
    families = ["render", "review"]

    def process(self, instance):
        context = instance.context
        creator_identifier = instance.data["creator_identifier"]
        if creator_identifier == "render.layer":
            self._collect_data_for_render_layer(instance)

        elif creator_identifier == "render.pass":
            self._collect_data_for_render_pass(instance)

        else:
            if creator_identifier == "scene.review":
                self._collect_data_for_review(instance)
            return

        subset_name = instance.data["subset"]
        instance.data["name"] = subset_name
        instance.data["label"] = "{} [{}-{}]".format(
            subset_name,
            context.data["sceneMarkIn"] + 1,
            context.data["sceneMarkOut"] + 1
        )

    def _collect_data_for_render_layer(self, instance):
        instance.data["families"].append("renderLayer")
        creator_attributes = instance.data["creator_attributes"]
        group_id = creator_attributes["group_id"]
        if creator_attributes["mark_for_review"]:
            instance.data["families"].append("review")

        layers_data = instance.context.data["layersData"]
        instance.data["layers"] = [
            copy.deepcopy(layer)
            for layer in layers_data
            if layer["group_id"] == group_id
        ]

    def _collect_data_for_render_pass(self, instance):
        instance.data["families"].append("renderPass")

        layer_names = set(instance.data["layer_names"])
        layers_data = instance.context.data["layersData"]

        creator_attributes = instance.data["creator_attributes"]
        if creator_attributes["mark_for_review"]:
            instance.data["families"].append("review")

        instance.data["layers"] = [
            copy.deepcopy(layer)
            for layer in layers_data
            if layer["name"] in layer_names
        ]

        render_layer_data = None
        render_layer_id = creator_attributes["render_layer_instance_id"]
        for in_data in instance.context.data["workfileInstances"]:
            if (
                in_data["creator_identifier"] == "render.layer"
                and in_data["instance_id"] == render_layer_id
            ):
                render_layer_data = in_data
                break

        instance.data["renderLayerData"] = copy.deepcopy(render_layer_data)
        # Invalid state
        if render_layer_data is None:
            return
        render_layer_name = render_layer_data["variant"]
        subset_name = instance.data["subset"]
        instance.data["subset"] = subset_name.format(
            **prepare_template_data({"renderlayer": render_layer_name})
        )

    def _collect_data_for_review(self, instance):
        instance.data["layers"] = copy.deepcopy(
            instance.context.data["layersData"]
        )
