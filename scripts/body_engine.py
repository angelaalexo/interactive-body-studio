import bpy
import os
import json
import webbrowser

TOP_SIZE_OBJECTS = {
    # Female
    "FEMALE_SLEEVELESS_SHIRT": {
        "S": ["Sleeveless_S"],
        "M": ["Sleeveless_M"],
        "L": ["Sleeveless_L"],
    },

    # Male
    "MALE_TSHIRT": {
        "S": ["Tshirt_S"],
        "M": ["Tshirt_M"],
        "L": ["Tshirt_L"],
    },
}

BOTTOM_SIZE_OBJECTS = {
    # Female
    "FEMALE_SKIRT": {
        "S": ["Female_Skirt_S", "S_S"],
        "M": ["Female_Skirt_M", "S_M"],
        "L": ["Female_Skirt_L", "S_L"],
    },

    # Male
    "MALE_SHORTS": {
        "S": ["Shorts_S"],
        "M": ["Shorts_M"],
        "L": ["Shorts_L"],
    },
}

GARMENT_SIZE_DATA = {
    # Female top
    "FEMALE_SLEEVELESS_SHIRT": {
        "label": "Female Sleeveless Shirt",
        "type": "TOP",
        "sizes": {
            "S": {"Chest": 88.0, "Waist": 70.0, "Length": 50.0},
            "M": {"Chest": 96.0, "Waist": 78.0, "Length": 50.0},
            "L": {"Chest": 106.0, "Waist": 90.0, "Length": 51.0},
        },
    },

    # Female bottom
    "FEMALE_SKIRT": {
        "label": "Female Skirt",
        "type": "BOTTOM",
        "sizes": {
            "S": {"Waist": 70.0, "Hips": 96.0, "Thighs": 56.0, "Length": 97.0},
            "M": {"Waist": 78.0, "Hips": 104.0, "Thighs": 62.0, "Length": 99.0},
            "L": {"Waist": 90.0, "Hips": 116.0, "Thighs": 68.0, "Length": 101.0},
        },
    },

    # Male top
    "MALE_TSHIRT": {
        "label": "Male T-Shirt",
        "type": "TOP",
        "sizes": {
            "S": {"Chest": 98.0, "Waist": 82.0, "Length": 68.0},
            "M": {"Chest": 106.0, "Waist": 90.0, "Length": 70.0},
            "L": {"Chest": 116.0, "Waist": 100.0, "Length": 72.0},
        },
    },

    # Male bottom
    "MALE_SHORTS": {
        "label": "Male Shorts",
        "type": "BOTTOM",
        "sizes": {
            "S": {"Waist": 82.0, "Hips": 98.0, "Thighs": 58.0, "Length": 50.0},
            "M": {"Waist": 90.0, "Hips": 106.0, "Thighs": 64.0, "Length": 52.0},
            "L": {"Waist": 100.0, "Hips": 116.0, "Thighs": 70.0, "Length": 54.0},
        },
    },
}

SIZE_ORDER = ["S", "M", "L"]


# =========================================================
# HELPERS
# =========================================================
def get_body_from_scene(context):
    """
    Return the active generated body without reading the dynamic wardrobe enums.

    Important: top_items()/bottom_items() are dynamic enum callbacks. Reading
    scene.top or scene.bottom from here can recursively call those callbacks and
    make Blender freeze or crash during UI redraw/selection.
    """
    active = context.view_layer.objects.active
    if active and active.type == "MESH" and active.get("gender") in {"female", "male"}:
        return active

    # Prefer a visible generated body.
    for name in ("Female Body", "Male Body"):
        obj = bpy.data.objects.get(name)
        if (
            obj
            and obj.type == "MESH"
            and obj.get("gender") in {"female", "male"}
            and not obj.hide_get()
            and not obj.hide_viewport
        ):
            return obj

    # Fall back to any generated body.
    for name in ("Female Body", "Male Body"):
        obj = bpy.data.objects.get(name)
        if obj and obj.type == "MESH" and obj.get("gender") in {"female", "male"}:
            return obj

    return None

def find_object(possible_names):
    for name in possible_names:
        obj = bpy.data.objects.get(name)
        if obj:
            return obj
    return None


def get_all_clothing_objects():
    objs = []
    for mapping in (TOP_SIZE_OBJECTS, BOTTOM_SIZE_OBJECTS):
        for item_id, sizes in mapping.items():
            for size_id, names in sizes.items():
                obj = find_object(names)
                if obj and obj not in objs:
                    objs.append(obj)
    return objs


_PREDICTION_UPDATE_RUNNING = False
_BODY_UPDATE_RUNNING = False
_CLOTHING_UPDATE_RUNNING = False
_CALLBACKS_SUSPENDED = False


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def predict_body_measurements(height_cm, weight_kg, gender="female"):
    """
    Predict practical body measurements from height and weight.

    These are calibrated estimates for this project, not medical measurements.
    The reference models are:
      Female: 160 cm, 57 kg
      Male:   180 cm, 78 kg
    """
    if gender == "male":
        height_delta = height_cm - 180.0
        weight_delta = weight_kg - 78.0

        return {
            "Waist": clamp(83.0 + weight_delta * 0.50 + height_delta * 0.06, 68.0, 125.0),
            "Chest": clamp(102.0 + weight_delta * 0.30 + height_delta * 0.10, 84.0, 135.0),
            "Hips": clamp(98.0 + weight_delta * 0.30 + height_delta * 0.07, 82.0, 125.0),
            "Thighs": clamp(59.0 + weight_delta * 0.20 + height_delta * 0.04, 46.0, 82.0),
        }

    height_delta = height_cm - 160.0
    weight_delta = weight_kg - 57.0

    return {
        "Waist": clamp(67.0 + weight_delta * 0.55 + height_delta * 0.05, 55.0, 115.0),
        "Chest": clamp(86.0 + weight_delta * 0.35 + height_delta * 0.08, 72.0, 125.0),
        "Hips": clamp(94.0 + weight_delta * 0.45 + height_delta * 0.08, 78.0, 130.0),
        "Thighs": clamp(54.0 + weight_delta * 0.25 + height_delta * 0.03, 42.0, 82.0),
    }


def update_height_weight(self, context):
    """Predict measurements once, then perform one body/clothing refresh."""
    global _PREDICTION_UPDATE_RUNNING

    if _CALLBACKS_SUSPENDED or _PREDICTION_UPDATE_RUNNING:
        return

    body = get_body_from_scene(context)
    if not body:
        return

    scene = context.scene
    _PREDICTION_UPDATE_RUNNING = True
    try:
        gender = body.get("gender", "female")
        predicted = predict_body_measurements(
            scene.engine_height,
            scene.engine_weight,
            gender,
        )

        # These assignments normally trigger four update callbacks. The global
        # guard makes those callbacks return immediately.
        scene.waist_cm = predicted["Waist"]
        scene.chest_cm = predicted["Chest"]
        scene.hips_cm = predicted["Hips"]
        scene.thighs_cm = predicted["Thighs"]
    finally:
        _PREDICTION_UPDATE_RUNNING = False

    # Perform exactly one expensive refresh.
    update_body_transform(None, context)

def get_effective_body_measurements(scene, gender="female"):
    """
    Return exactly the measurements displayed in the panel.

    No hidden weight adjustment is added here. The visible values are the
    single source of truth for both body deformation and size recommendation.
    """
    return {
        "Chest": scene.chest_cm,
        "Waist": scene.waist_cm,
        "Hips": scene.hips_cm,
        "Thighs": scene.thighs_cm,
    }


def evaluate_size(scene, item_id, size_id, gender="female"):
    garment = GARMENT_SIZE_DATA.get(item_id)
    if not garment:
        return {"score": 0, "status": "No data", "icon": "INFO", "details": []}

    body = get_effective_body_measurements(scene, gender)
    data = garment["sizes"][size_id]

    details = []
    penalty = 0.0
    too_tight = False
    loose_count = 0
    checked_parts = 0

    for part, garment_cm in data.items():
        if part == "Length":
            continue

        checked_parts += 1
        body_cm = body.get(part, 0.0)
        ease = garment_cm - body_cm

        if ease < 0:
            too_tight = True
            details.append(f"{part}: {abs(ease):.1f} cm too tight")
            penalty += abs(ease) * 2.0
        elif ease <= 3:
            details.append(f"{part}: slim fit, {ease:.1f} cm ease")
            penalty += (3 - ease) * 1.0
        elif ease <= 8:
            details.append(f"{part}: regular fit, {ease:.1f} cm ease")
            penalty += abs(ease - 5) * 0.5
        else:
            loose_count += 1
            details.append(f"{part}: loose, {ease:.1f} cm ease")
            penalty += (ease - 8) * 2.0

    score = max(0, min(100, round(100 - penalty)))

    if too_tight:
        status = "Too tight"
        icon = "ERROR"
    elif loose_count >= checked_parts and checked_parts > 0:
        status = "Too loose"
        icon = "INFO"
    elif loose_count > 0:
        status = "Relaxed fit"
        icon = "INFO"
    else:
        status = "Good fit"
        icon = "CHECKMARK"

    return {"score": score, "status": status, "icon": icon, "details": details}


def recommend_size(scene, item_id, gender="female"):
    """
    Return the best suitable size.

    If every available size is too tight, return None instead of misleadingly
    recommending the largest size.
    """

    results = {
        size_id: evaluate_size(scene, item_id, size_id, gender)
        for size_id in SIZE_ORDER
    }

    suitable_sizes = [
        size_id
        for size_id in SIZE_ORDER
        if results[size_id]["status"] != "Too tight"
    ]

    if not suitable_sizes:
        return None

    best = max(
        suitable_sizes,
        key=lambda size_id: results[size_id]["score"]
    )
    best_score = results[best]["score"]

    # Prefer a slightly larger comfortable size when the scores are very close.
    for size_id in suitable_sizes:
        if SIZE_ORDER.index(size_id) > SIZE_ORDER.index(best):
            if (
                best_score - results[size_id]["score"] <= 3
                and results[size_id]["status"] != "Too loose"
            ):
                best = size_id
                best_score = results[size_id]["score"]

    return best

def selected_or_recommended_size(scene, item_id, kind, gender="female"):
    if kind == "TOP":
        if scene.top_size_mode != "AUTO":
            return scene.top_size_mode
    else:
        if scene.bottom_size_mode != "AUTO":
            return scene.bottom_size_mode

    recommended = recommend_size(scene, item_id, gender)

    # Keep showing the largest garment for visual comparison when nothing fits,
    # while the panel clearly reports "No suitable size".
    return recommended if recommended is not None else "L"


def hide_object(obj):
    if obj:
        obj.hide_set(True)
        obj.hide_viewport = True
        obj.hide_render = True


def show_object(obj, body=None):
    if not obj:
        return

    # Disable expensive legacy modifiers BEFORE making the object visible.
    # Unhiding first can force Blender to evaluate Surface Deform/Cloth and
    # freeze before the script reaches the modifier-disable code.
    for mod in obj.modifiers:
        if mod.type in {"SHRINKWRAP", "SURFACE_DEFORM", "CLOTH", "SUBSURF"}:
            mod.show_viewport = False
            mod.show_render = False

    # Remove old parent without changing world position.
    if obj.parent:
        world_matrix = obj.matrix_world.copy()
        obj.parent = None
        obj.matrix_world = world_matrix

    # Save each garment's original transform only once.
    if "_base_scale_x" not in obj:
        obj["_base_scale_x"] = obj.scale.x
        obj["_base_scale_y"] = obj.scale.y
        obj["_base_scale_z"] = obj.scale.z
        obj["_base_location_x"] = obj.location.x
        obj["_base_location_y"] = obj.location.y
        obj["_base_location_z"] = obj.location.z

    if body:
        gender = body.get("gender", "female")
        base_height = 180.0 if gender == "male" else 160.0
        height_factor = bpy.context.scene.engine_height / base_height

        obj.scale.x = obj["_base_scale_x"]
        obj.scale.y = obj["_base_scale_y"]
        obj.scale.z = obj["_base_scale_z"] * height_factor
        obj.location.x = obj["_base_location_x"]
        obj.location.y = obj["_base_location_y"]
        obj.location.z = obj["_base_location_z"] * height_factor

    obj.hide_set(False)
    obj.hide_viewport = False
    obj.hide_render = False

# =========================================================
# BODY UPDATE
# =========================================================
def update_body_transform(self, context):
    global _BODY_UPDATE_RUNNING

    if _CALLBACKS_SUSPENDED or _PREDICTION_UPDATE_RUNNING or _BODY_UPDATE_RUNNING:
        return

    body = get_body_from_scene(context)
    if not body:
        return

    _BODY_UPDATE_RUNNING = True
    try:

        scene = context.scene
        h_cm = scene.engine_height
        w_kg = scene.engine_weight
        gender = body.get("gender", "female")

        if gender == "male":
            base_height = 180.0
            base_weight = 78.0
            base_values = {
                "Waist": 83.0,
                "Chest": 102.0,
                "Hips": 98.0,
                "Thighs": 59.0,
            }
        else:
            base_height = 160.0
            base_weight = 57.0
            base_values = {
                "Waist": 67.0,
                "Chest": 86.0,
                "Hips": 94.0,
                "Thighs": 54.0,
            }

        # Height changes vertical scale only. Weight is represented through the
        # predicted body-part measurements, so it is not applied twice.
        body.location.z = 0.0
        body.scale = (1.0, 1.0, h_cm / base_height)

        weight_delta = w_kg - base_weight

        parts = {
            "Waist": {"val": scene.waist_cm, "base": base_values["Waist"]},
            "Chest": {"val": scene.chest_cm, "base": base_values["Chest"]},
            "Hips": {"val": scene.hips_cm, "base": base_values["Hips"]},
            "Thighs": {"val": scene.thighs_cm, "base": base_values["Thighs"]},
        }

        if gender == "male":
            parts.update({
                "Belly": {"val": 70.0 + weight_delta * 0.42, "base": 70.0},
                "Buttocks": {"val": 70.0 + weight_delta * 0.18, "base": 70.0},
                "UpperArms": {"val": 70.0 + weight_delta * 0.10, "base": 70.0},
                "Forearms": {"val": 70.0 + weight_delta * 0.04, "base": 70.0},
                "Calves": {"val": 70.0 + weight_delta * 0.06, "base": 70.0},
                "Neck": {"val": 70.0 + weight_delta * 0.05, "base": 70.0},
            })
        else:
            parts.update({
                "Belly": {"val": 70.0 + weight_delta * 0.38, "base": 70.0},
                "Buttocks": {"val": 70.0 + weight_delta * 0.28, "base": 70.0},
                "UpperArms": {"val": 70.0 + weight_delta * 0.08, "base": 70.0},
                "Forearms": {"val": 70.0 + weight_delta * 0.03, "base": 70.0},
                "Calves": {"val": 70.0 + weight_delta * 0.05, "base": 70.0},
                "Neck": {"val": 70.0 + weight_delta * 0.03, "base": 70.0},
            })

        strength_map = {
            "Waist": 0.0006,
            "Chest": 0.0006,
            "Hips": 0.0006,
            "Thighs": 0.0008,
            "Belly": 0.004,
            "Buttocks": 0.0006,
            "UpperArms": 0.0005,
            "Forearms": 0.0003,
            "Calves": 0.0004,
            "Neck": 0.0003,
        }

        for name, config in parts.items():
            mod_name = f"{name}_Displace"

            if mod_name not in body.modifiers:
                mod = body.modifiers.new(name=mod_name, type="DISPLACE")
                mod.vertex_group = name
                mod.mid_level = 0.0

            body.modifiers[mod_name].strength = (
                config["val"] - config["base"]
            ) * strength_map.get(name, 0.0008)

        apply_skin_material(scene, body)
        update_clothing(None, context)
    finally:
        _BODY_UPDATE_RUNNING = False


def apply_skin_material(scene, body):
    mat_name = "Character_Skin"
    mat = bpy.data.materials.get(mat_name)
    if not mat:
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True

    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        skin_map = {
            "FAIR": (0.82, 0.66, 0.55),
            "LIGHT": (0.72, 0.55, 0.42),
            "TAN": (0.58, 0.42, 0.30),
            "DARK": (0.35, 0.22, 0.16),
            "BLACK": (0.18, 0.12, 0.09),
        }
        color = skin_map.get(scene.skin_type, (0.8, 0.6, 0.5))
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = 0.55
        if "Subsurface" in bsdf.inputs:
            bsdf.inputs["Subsurface"].default_value = 0.12
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.35

    if len(body.data.materials) == 0:
        body.data.materials.append(mat)
    else:
        body.data.materials[0] = mat


# =========================================================
# CLOTHING UPDATE
# =========================================================
def update_clothing(self, context):
    global _CLOTHING_UPDATE_RUNNING

    if _CALLBACKS_SUSPENDED or _CLOTHING_UPDATE_RUNNING:
        return

    body = get_body_from_scene(context)
    if not body:
        return

    _CLOTHING_UPDATE_RUNNING = True
    try:
        scene = context.scene
        gender = body.get("gender", "female")

        # Make parent collections visible.
        for col_name in [
            "Clothing",
            "Female", "Female_Top", "Female_Bottom", "Sleeveless Top", "Skirt",
            "Male", "Male_Top", "Male_Bottom", "Tshirt", "Shorts"
        ]:
            col = bpy.data.collections.get(col_name)
            if col:
                col.hide_viewport = False
                col.hide_render = False

        # Hide all S/M/L clothing objects first.
        for obj in get_all_clothing_objects():
            hide_object(obj)

        if scene.top in TOP_SIZE_OBJECTS:
            size_id = selected_or_recommended_size(scene, scene.top, "TOP", gender)
            obj = find_object(TOP_SIZE_OBJECTS[scene.top][size_id])
            show_object(obj, body)

        if scene.bottom in BOTTOM_SIZE_OBJECTS:
            size_id = selected_or_recommended_size(scene, scene.bottom, "BOTTOM", gender)
            obj = find_object(BOTTOM_SIZE_OBJECTS[scene.bottom][size_id])
            show_object(obj, body)

        # tag_redraw is much cheaper than forcing a full dependency-graph update.
        for area in context.screen.areas if context.screen else []:
            if area.type == "VIEW_3D":
                area.tag_redraw()
    finally:
        _CLOTHING_UPDATE_RUNNING = False


# =========================================================
# WEBSITE EXPORT
# =========================================================
def get_selected_garment_object(scene, item_id, kind, gender):
    if item_id == "NONE":
        return None, None
    mapping = TOP_SIZE_OBJECTS if kind == "TOP" else BOTTOM_SIZE_OBJECTS
    if item_id not in mapping:
        return None, None
    size_id = selected_or_recommended_size(scene, item_id, kind, gender)
    return find_object(mapping[item_id][size_id]), size_id


def get_current_export_objects(context):
    body = get_body_from_scene(context)
    if not body:
        return None, [], {}

    scene = context.scene
    gender = body.get("gender", "female")
    export_objects = [body]
    metadata = {
        "gender": gender,
        "height": round(scene.engine_height, 2),
        "weight": round(scene.engine_weight, 2),
        "chest": round(scene.chest_cm, 2),
        "waist": round(scene.waist_cm, 2),
        "hips": round(scene.hips_cm, 2),
        "thighs": round(scene.thighs_cm, 2),
        "skin": scene.skin_type,
        "top": None,
        "bottom": None,
    }

    top_obj, top_size = get_selected_garment_object(scene, scene.top, "TOP", gender)
    if top_obj:
        export_objects.append(top_obj)
        result = evaluate_size(scene, scene.top, top_size, gender)
        metadata["top"] = {
            "label": GARMENT_SIZE_DATA[scene.top]["label"],
            "size": top_size,
            "status": result["status"],
            "score": result["score"],
        }

    bottom_obj, bottom_size = get_selected_garment_object(scene, scene.bottom, "BOTTOM", gender)
    if bottom_obj:
        export_objects.append(bottom_obj)
        result = evaluate_size(scene, scene.bottom, bottom_size, gender)
        metadata["bottom"] = {
            "label": GARMENT_SIZE_DATA[scene.bottom]["label"],
            "size": bottom_size,
            "status": result["status"],
            "score": result["score"],
        }

    return body, export_objects, metadata


class BODY_OT_export_current_character(bpy.types.Operator):
    bl_idname = "body.export_current_character"
    bl_label = "Export Current Character"
    bl_description = "Export the active body and visible clothes to the website"

    def execute(self, context):
        body, export_objects, metadata = get_current_export_objects(context)
        if not body:
            self.report({"ERROR"}, "No generated character was found.")
            return {"CANCELLED"}

        website_folder = bpy.path.abspath(context.scene.website_folder).strip()
        if not website_folder:
            self.report({"ERROR"}, "Choose the website folder first.")
            return {"CANCELLED"}

        if not os.path.isfile(os.path.join(website_folder, "index.html")):
            self.report({"ERROR"}, "The selected folder does not contain index.html.")
            return {"CANCELLED"}

        models_folder = os.path.join(website_folder, "models")
        os.makedirs(models_folder, exist_ok=True)
        model_path = os.path.join(models_folder, "current_character.glb")
        data_path = os.path.join(models_folder, "current_character.json")

        previous_active = context.view_layer.objects.active
        previous_selected = list(context.selected_objects)
        previous_visibility = {
            obj.name: (obj.hide_get(), obj.hide_viewport, obj.hide_render)
            for obj in export_objects
        }

        try:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")

            bpy.ops.object.select_all(action="DESELECT")

            for obj in export_objects:
                obj.hide_set(False)
                obj.hide_viewport = False
                obj.hide_render = False
                obj.select_set(True)

            context.view_layer.objects.active = body
            context.view_layer.update()

            bpy.ops.export_scene.gltf(
                filepath=model_path,
                export_format="GLB",
                use_selection=True,
                export_apply=True,
                export_animations=False,
                export_cameras=False,
                export_lights=False,
            )

            with open(data_path, "w", encoding="utf-8") as file:
                json.dump(metadata, file, indent=2)

        except Exception as error:
            self.report({"ERROR"}, f"Export failed: {error}")
            return {"CANCELLED"}

        finally:
            bpy.ops.object.select_all(action="DESELECT")

            for obj_name, state in previous_visibility.items():
                obj = bpy.data.objects.get(obj_name)
                if obj:
                    obj.hide_set(state[0])
                    obj.hide_viewport = state[1]
                    obj.hide_render = state[2]

            for obj in previous_selected:
                if obj and obj.name in bpy.data.objects:
                    try:
                        obj.select_set(True)
                    except RuntimeError:
                        pass

            if previous_active and previous_active.name in bpy.data.objects:
                context.view_layer.objects.active = previous_active

        self.report({"INFO"}, "Exported current_character.glb and current_character.json")
        return {"FINISHED"}


class BODY_OT_open_project_website(bpy.types.Operator):
    bl_idname = "body.open_project_website"
    bl_label = "Open Project Website"

    def execute(self, context):
        url = context.scene.website_url.strip()
        if not url:
            self.report({"ERROR"}, "Enter the website URL first.")
            return {"CANCELLED"}
        webbrowser.open(url)
        return {"FINISHED"}


class BODY_OT_open_website_folder(bpy.types.Operator):
    bl_idname = "body.open_website_folder"
    bl_label = "Open Website Folder"

    def execute(self, context):
        folder = bpy.path.abspath(context.scene.website_folder).strip()
        if not folder or not os.path.isdir(folder):
            self.report({"ERROR"}, "Website folder was not found.")
            return {"CANCELLED"}
        os.startfile(folder)
        return {"FINISHED"}


# =========================================================
# OPERATORS
# =========================================================
class MESH_OT_create_female(bpy.types.Operator):
    bl_idname = "mesh.create_female"
    bl_label = "Create Female"

    def execute(self, context):
        template = bpy.data.objects.get("Female base")
        if not template:
            self.report({"ERROR"}, "Female base model template not found.")
            return {"CANCELLED"}

        new_obj = template.copy()
        new_obj.data = template.data.copy()
        context.collection.objects.link(new_obj)
        new_obj.name = "Female Body"
        new_obj["gender"] = "female"

        context.view_layer.objects.active = new_obj
        new_obj.select_set(True)
        context.view_layer.update()

        global _CALLBACKS_SUSPENDED
        _CALLBACKS_SUSPENDED = True
        try:
            context.scene.engine_height = 160.0
            context.scene.engine_weight = 57.0
            context.scene.waist_cm = 67.0
            context.scene.chest_cm = 86.0
            context.scene.hips_cm = 94.0
            context.scene.thighs_cm = 54.0
            reset_wardrobe_for_gender(context.scene, "female")
        finally:
            _CALLBACKS_SUSPENDED = False

        update_body_transform(None, context)
        return {"FINISHED"}


class MESH_OT_create_male(bpy.types.Operator):
    bl_idname = "mesh.create_male"
    bl_label = "Create Male"

    def execute(self, context):
        template = bpy.data.objects.get("Male Base") or bpy.data.objects.get("Male base")
        if not template:
            self.report({"ERROR"}, "Male base model template not found.")
            return {"CANCELLED"}

        new_obj = template.copy()
        new_obj.data = template.data.copy()
        context.collection.objects.link(new_obj)
        new_obj.name = "Male Body"
        new_obj["gender"] = "male"

        context.view_layer.objects.active = new_obj
        new_obj.select_set(True)
        context.view_layer.update()

        global _CALLBACKS_SUSPENDED
        _CALLBACKS_SUSPENDED = True
        try:
            context.scene.engine_height = 180.0
            context.scene.engine_weight = 78.0
            context.scene.waist_cm = 83.0
            context.scene.chest_cm = 102.0
            context.scene.hips_cm = 98.0
            context.scene.thighs_cm = 59.0
            reset_wardrobe_for_gender(context.scene, "male")
        finally:
            _CALLBACKS_SUSPENDED = False

        update_body_transform(None, context)
        return {"FINISHED"}


class MESH_OT_reset_body_transform(bpy.types.Operator):
    bl_idname = "mesh.reset_body_transform"
    bl_label = "Reset Character"

    def execute(self, context):
        scene = context.scene
        body = get_body_from_scene(context)

        global _CALLBACKS_SUSPENDED
        _CALLBACKS_SUSPENDED = True
        try:
            if body and body.get("gender") == "male":
                scene.engine_height = 180.0
                scene.engine_weight = 78.0
                scene.waist_cm = 83.0
                scene.chest_cm = 102.0
                scene.hips_cm = 98.0
                scene.thighs_cm = 59.0
            else:
                scene.engine_height = 160.0
                scene.engine_weight = 57.0
                scene.waist_cm = 67.0
                scene.chest_cm = 86.0
                scene.hips_cm = 94.0
                scene.thighs_cm = 54.0

            scene.top_size_mode = "AUTO"
            scene.bottom_size_mode = "AUTO"
        finally:
            _CALLBACKS_SUSPENDED = False

        update_body_transform(None, context)
        return {"FINISHED"}


class SCENE_OT_set_skin(bpy.types.Operator):
    bl_idname = "scene.set_skin"
    bl_label = "Set Skin Variant"

    skin: bpy.props.StringProperty()

    def execute(self, context):
        context.scene.skin_type = self.skin
        return {"FINISHED"}


# =========================================================
# UI
# =========================================================
def draw_fit_box(layout, scene, item_id, kind, gender="female"):
    if item_id == "NONE":
        return

    garment = GARMENT_SIZE_DATA[item_id]
    rec_size = recommend_size(scene, item_id, gender)
    selected_size = selected_or_recommended_size(scene, item_id, kind, gender)
    result = evaluate_size(scene, item_id, selected_size, gender)

    box = layout.box()
    box.label(text=f"{kind.capitalize()} Fit Analysis", icon="MOD_CLOTH")
    box.label(text=f"Item: {garment['label']}")
    if rec_size is None:
        box.label(text="Recommended: No suitable size", icon="ERROR")
    else:
        box.label(text=f"Recommended: {rec_size}", icon="SOLO_ON")
    box.label(text=f"Showing: {selected_size} | {result['status']} | Score {result['score']}%", icon=result["icon"])

    for detail in result["details"]:
        box.label(text=f"• {detail}")

    col = box.column(align=True)
    col.label(text="Size comparison:")
    for size_id in SIZE_ORDER:
        r = evaluate_size(scene, item_id, size_id, gender)
        prefix = "⭐ " if rec_size is not None and size_id == rec_size else ""
        col.label(text=f"{prefix}{size_id}: {r['status']} ({r['score']}%)", icon=r["icon"])


class ATELIER_PT_Panel(bpy.types.Panel):
    bl_label = "INTERACTIVE BODY STUDIO"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BODY ENGINE"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        body = get_body_from_scene(context)
        gender = body.get("gender", "female") if body else "female"

        header = layout.box()
        header.label(text="Current Character Workspace", icon="COMMUNITY")
        if body:
            header.label(text=f"Height Dimension: {body.dimensions.z:.2f} m")
            header.label(text=f"Gender Target: {gender.capitalize()}")
        else:
            header.label(text="No active character selected", icon="ERROR")

        layout.separator()

        box = layout.box()
        box.prop(scene, "show_create", text="Create Character", emboss=False, icon="TRIA_DOWN")
        if scene.show_create:
            row = box.row(align=True)
            row.operator("mesh.create_female", icon="OUTLINER_OB_ARMATURE")
            row.operator("mesh.create_male", icon="OUTLINER_OB_ARMATURE")

        layout.separator()

        box = layout.box()
        box.prop(scene, "show_body", text="Height & Weight", emboss=False, icon="TRIA_DOWN")
        if scene.show_body:
            box.prop(scene, "engine_height")
            box.prop(scene, "engine_weight")
            box.label(text="Measurements update automatically", icon="INFO")
            box.operator("mesh.reset_body_transform", icon="FILE_REFRESH")

        layout.separator()

        box = layout.box()
        box.prop(scene, "show_proportions", text="Adjust Body Proportions", emboss=False, icon="TRIA_DOWN")
        if scene.show_proportions:
            grid = box.grid_flow(columns=2, align=True)
            grid.prop(scene, "waist_cm")
            grid.prop(scene, "chest_cm")
            grid.prop(scene, "hips_cm")
            grid.prop(scene, "thighs_cm")

        layout.separator()

        box = layout.box()
        box.label(text="Skin Pigment Variant", icon="MOD_SKIN")
        row = box.row(align=True)
        for key, name in {
            "FAIR": "Fair",
            "LIGHT": "Light",
            "TAN": "Tan",
            "DARK": "Dark",
            "BLACK": "Black",
        }.items():
            op = row.operator("scene.set_skin", text=name, depress=(scene.skin_type == key))
            op.skin = key

        layout.separator()

        box = layout.box()
        box.label(text="Wardrobe Management", icon="MOD_CLOTH")
        box.label(text=f"{gender.capitalize()} wardrobe", icon="USER")
        box.prop(scene, "top")
        if scene.top in TOP_SIZE_OBJECTS:
            box.prop(scene, "top_size_mode", text="Top Size")

        box.prop(scene, "bottom")
        if scene.bottom in BOTTOM_SIZE_OBJECTS:
            box.prop(scene, "bottom_size_mode", text="Bottom Size")

        if scene.top != "NONE":
            draw_fit_box(layout, scene, scene.top, "TOP", gender)

        if scene.bottom != "NONE":
            draw_fit_box(layout, scene, scene.bottom, "BOTTOM", gender)

        layout.separator()

        web_box = layout.box()
        web_box.label(text="Website Export", icon="URL")
        web_box.prop(scene, "website_folder", text="Folder")
        web_box.prop(scene, "website_url", text="URL")
        web_box.operator("body.export_current_character", icon="EXPORT")

        row = web_box.row(align=True)
        row.operator("body.open_project_website", icon="URL")
        row.operator("body.open_website_folder", text="Open Folder", icon="FILE_FOLDER")

        web_box.label(text="Exports current_character.glb + JSON", icon="INFO")



# =========================================================
# GENDER-SPECIFIC WARDROBE MENUS
# =========================================================
def get_current_gender(context):
    body = get_body_from_scene(context)
    if body:
        return body.get("gender", "female")
    return "female"


def top_items(self, context):
    if get_current_gender(context) == "male":
        return [
            ("NONE", "None", "No top"),
            ("MALE_TSHIRT", "Male T-Shirt", "Male T-shirt"),
        ]

    return [
        ("NONE", "None", "No top"),
        ("FEMALE_SLEEVELESS_SHIRT", "Female Sleeveless Shirt", "Female sleeveless shirt"),
    ]


def bottom_items(self, context):
    if get_current_gender(context) == "male":
        return [
            ("NONE", "None", "No bottom"),
            ("MALE_SHORTS", "Male Shorts", "Male shorts"),
        ]

    return [
        ("NONE", "None", "No bottom"),
        ("FEMALE_SKIRT", "Female Skirt", "Female skirt"),
    ]


def reset_wardrobe_for_gender(scene, gender):
    if gender == "male":
        if scene.top not in {"NONE", "MALE_TSHIRT"}:
            scene.top = "NONE"
        if scene.bottom not in {"NONE", "MALE_SHORTS"}:
            scene.bottom = "NONE"
    else:
        if scene.top not in {"NONE", "FEMALE_SLEEVELESS_SHIRT"}:
            scene.top = "NONE"
        if scene.bottom not in {"NONE", "FEMALE_SKIRT"}:
            scene.bottom = "NONE"

    scene.top_size_mode = "AUTO"
    scene.bottom_size_mode = "AUTO"


# =========================================================
# REGISTRATION
# =========================================================
classes = (
    MESH_OT_create_female,
    MESH_OT_create_male,
    MESH_OT_reset_body_transform,
    SCENE_OT_set_skin,
    BODY_OT_export_current_character,
    BODY_OT_open_project_website,
    BODY_OT_open_website_folder,
    ATELIER_PT_Panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.engine_height = bpy.props.FloatProperty(
        name="Height (cm)", default=160.0, min=155.0, max=190.0,
        update=update_height_weight
    )
    bpy.types.Scene.engine_weight = bpy.props.FloatProperty(
        name="Weight (kg)", default=57.0, min=55.0, max=95.0,
        update=update_height_weight
    )
    bpy.types.Scene.waist_cm = bpy.props.FloatProperty(
        name="Waist", default=67.0, min=58.0, max=110.0, update=update_body_transform
    )
    bpy.types.Scene.chest_cm = bpy.props.FloatProperty(
        name="Chest", default=86.0, min=70.0, max=130.0, update=update_body_transform
    )
    bpy.types.Scene.hips_cm = bpy.props.FloatProperty(
        name="Hips", default=94.0, min=75.0, max=130.0, update=update_body_transform
    )
    bpy.types.Scene.thighs_cm = bpy.props.FloatProperty(
        name="Thighs", default=54.0, min=40.0, max=80.0, update=update_body_transform
    )

    bpy.types.Scene.skin_type = bpy.props.EnumProperty(
        items=[
            ("FAIR", "Fair", ""),
            ("LIGHT", "Light", ""),
            ("TAN", "Tan", ""),
            ("DARK", "Dark", ""),
            ("BLACK", "Black", ""),
        ],
        default="LIGHT",
        update=update_body_transform,
    )

    bpy.types.Scene.show_create = bpy.props.BoolProperty(default=True)
    bpy.types.Scene.show_body = bpy.props.BoolProperty(default=True)
    bpy.types.Scene.show_proportions = bpy.props.BoolProperty(default=True)

    default_website_folder = os.path.join(
        os.path.expanduser("~"),
        "Documents",
        "interactive_body_website_dashboard",
    )

    bpy.types.Scene.website_folder = bpy.props.StringProperty(
        name="Website Folder",
        description="Folder containing index.html and the models folder",
        subtype="DIR_PATH",
        default=default_website_folder,
    )

    bpy.types.Scene.website_url = bpy.props.StringProperty(
        name="Website URL",
        description="Local or published website address",
        default="http://localhost:8000",
    )

    bpy.types.Scene.top = bpy.props.EnumProperty(
        name="Top",
        items=top_items,
        update=update_clothing,
    )

    bpy.types.Scene.bottom = bpy.props.EnumProperty(
        name="Bottom",
        items=bottom_items,
        update=update_clothing,
    )

    bpy.types.Scene.top_size_mode = bpy.props.EnumProperty(
        name="Top Size",
        default="AUTO",
        items=[
            ("AUTO", "Auto Recommended", ""),
            ("S", "Small", ""),
            ("M", "Medium", ""),
            ("L", "Large", ""),
        ],
        update=update_clothing,
    )

    bpy.types.Scene.bottom_size_mode = bpy.props.EnumProperty(
        name="Bottom Size",
        default="AUTO",
        items=[
            ("AUTO", "Auto Recommended", ""),
            ("S", "Small", ""),
            ("M", "Medium", ""),
            ("L", "Large", ""),
        ],
        update=update_clothing,
    )

def unregister():
    for cls in reversed(classes):
        registered_cls = getattr(bpy.types, cls.__name__, None)
        if registered_cls:
            try:
                bpy.utils.unregister_class(registered_cls)
            except RuntimeError:
                pass

    for prop_name in (
        "engine_height", "engine_weight", "waist_cm", "chest_cm",
        "hips_cm", "thighs_cm", "skin_type", "show_create",
        "show_body", "show_proportions", "website_folder",
        "website_url", "top", "bottom", "top_size_mode",
        "bottom_size_mode",
    ):
        if hasattr(bpy.types.Scene, prop_name):
            try:
                delattr(bpy.types.Scene, prop_name)
            except Exception:
                pass


if __name__ == "__main__":
    unregister()
    register()
