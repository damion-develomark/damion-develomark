"""Drop the language pie and the contribution radar from the 3D skyline SVGs,
keeping the 3D calendar and the totals line."""
import pathlib, re
import xml.etree.ElementTree as ET

NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)
for path in pathlib.Path("profile-3d-contrib").glob("*.svg"):
    tree = ET.parse(path)
    root = tree.getroot()
    for child in list(root):
        transform = child.get("transform") or ""
        # The radar sits at translate(980, …) and the pie at translate(40, 520).
        if child.tag == f"{{{NS}}}g" and re.match(r"translate\((980|40)\s*,", transform):
            root.remove(child)
    tree.write(path, encoding="unicode")
