"""Apply an uploaded master/layout design while retaining editable slide objects.

Template example slides are deliberately not copied. Source content is grouped and
scaled uniformly into the template's content area, so charts, pictures and tables
retain their aspect ratios and relationships. This is deterministic template
application rather than semantic redesign of arbitrary slide content.
"""
from __future__ import annotations

import io
import os
import posixpath
import tempfile
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

from lxml import etree as ET

from .assembly import (
    A, CT, MAIN, P, PRES, R, REL, RID, _Draft, _Source, _dims, _parse,
    _read_rels, _relations, _rel, _rels_name, _xml,
)

POTX_MAIN = "application/vnd.openxmlformats-officedocument.presentationml.template.main+xml"
NOTICE = (
    "Applied the template's master, layout, theme and page size. Explicit source "
    "fonts, colours and object formatting are retained. Review text fit and layout in PowerPoint."
)
SAMPLES = "Template example slides and artwork placed only on those slides are not copied."


class _TemplateZip:
    """Normalize only a standard POTX's main type for the guarded source reader."""
    def __init__(self, archive):
        self.archive = archive

    def namelist(self):
        return self.archive.namelist()

    def infolist(self):
        return self.archive.infolist()

    def read(self, name):
        data = self.archive.read(name)
        if name == "[Content_Types].xml":
            node = _parse(data)
            for item in node:
                if item.get("PartName") == "/" + PRES and item.get("ContentType") == POTX_MAIN:
                    item.set("ContentType", MAIN)
            return _xml(node)
        return data


def _open_template(stack, path):
    path = Path(path)
    if path.suffix.lower() not in {".pptx", ".potx"}:
        raise ValueError("Upload a standard .pptx or .potx PowerPoint template.")
    archive = stack.enter_context(ZipFile(path))
    # _Source reuses the assembler's package, macro, DTD and size guards.
    source = _Source(_TemplateZip(archive))
    return source


def _layouts(source):
    result = []
    for master in source.root.findall(P + "sldMasterIdLst/" + P + "sldMasterId"):
        kind, part, external = source.manifest[master.get(RID)]
        if external or kind != R + "/slideMaster":
            raise ValueError("Invalid template master relationship.")
        node = _parse(source.zip.read(part))
        if node.tag != P + "sldMaster":
            raise ValueError("Invalid template master.")
        rels = source.rels(part)
        for entry in node.findall(P + "sldLayoutIdLst/" + P + "sldLayoutId"):
            kind, layout, external = rels[entry.get(RID)]
            if external or kind != R + "/slideLayout":
                raise ValueError("Invalid template layout relationship.")
            layout_node = _parse(source.zip.read(layout))
            if layout_node.tag != P + "sldLayout":
                raise ValueError("Invalid template layout.")
            result.append((layout, layout_node, part, node))
    if not result:
        raise ValueError("The template needs at least one slide master and layout.")
    return result


def inspect_template(path: Path) -> dict:
    """Validate a template's design graph and return safe display metadata."""
    try:
        with ExitStack() as stack:
            source = _open_template(stack, path)
            layouts = _layouts(source)
            width, height = _dims(source.root.find(P + "sldSz"))
            source.layouts.update(item[0] for item in layouts)
            # Copy the design graph to exercise exactly the same allowlist as drafts.
            with ZipFile(io.BytesIO(), "w", compression=ZIP_DEFLATED) as sink:
                draft = _Draft(sink)
                for part, *_ in layouts:
                    draft.copy(source, part)
            names = [node.find(P + "cSld").get("name", node.get("type", "Layout"))
                     for _, node, _, _ in layouts]
            return {"slideWidth": width, "slideHeight": height, "layoutNames": names,
                    "warnings": sorted({NOTICE, SAMPLES, *draft.warnings})}
    except (BadZipFile, ET.XMLSyntaxError, KeyError, TypeError, AttributeError,
            OSError, RuntimeError, EOFError) as exc:
        raise ValueError("The PowerPoint template is invalid or unsupported.") from exc


def _placeholder(shape):
    return shape.find(".//" + P + "ph")


def _role(shape):
    ph = _placeholder(shape)
    return ph.get("type", "obj") if ph is not None else None


def _tree(node):
    return node.find(P + "cSld/" + P + "spTree")


def _shape_transform(shape):
    for path in (P + "spPr/" + A + "xfrm", P + "xfrm", P + "grpSpPr/" + A + "xfrm"):
        node = shape.find(path)
        if node is not None:
            return node
    return None


def _inherited_shape(shape, layout, master):
    ph = _placeholder(shape)
    if ph is None:
        return []
    idx, role = ph.get("idx", "0"), ph.get("type", "obj")
    inherited = []
    for node in (layout, master):
        candidates = list(_tree(node))
        match = next((s for s in candidates if _placeholder(s) is not None
                      and _placeholder(s).get("idx", "0") == idx), None)
        if node is master:
            match = next((s for s in candidates if _role(s) == role), match)
        if match is not None:
            inherited.append(match)
    return inherited


def _resolved_transform(shape, layout, master):
    result = _shape_transform(shape)
    result = deepcopy(result) if result is not None else ET.Element(A + "xfrm")
    for candidate in _inherited_shape(shape, layout, master):
        transform = _shape_transform(candidate)
        if transform is not None:
            for tag in ("off", "ext"):
                if result.find(A + tag) is None and transform.find(A + tag) is not None:
                    result.append(deepcopy(transform.find(A + tag)))
    if result.find(A + "off") is None or result.find(A + "ext") is None:
        raise ValueError("A source object has unsupported inherited geometry.")
    return result


def _bounds(transform):
    off, ext = transform.find(A + "off"), transform.find(A + "ext")
    return tuple(int(off.get(k)) for k in ("x", "y")) + tuple(int(ext.get(k)) for k in ("cx", "cy"))


def _set_transform(shape, transform):
    if shape.tag in {P + "sp", P + "pic", P + "cxnSp"}:
        parent = shape.find(P + "spPr")
        tag = A + "xfrm"
    elif shape.tag == P + "grpSp":
        parent = shape.find(P + "grpSpPr")
        tag = A + "xfrm"
    elif shape.tag == P + "graphicFrame":
        old = shape.find(P + "xfrm")
        if old is not None:
            shape.remove(old)
        transform.tag = P + "xfrm"
        shape.insert(1, transform)
        return
    else:
        raise ValueError("A source slide contains an unsupported drawing object.")
    if parent is None:
        raise ValueError("A source object is missing its shape properties.")
    old = parent.find(tag)
    if old is not None:
        parent.remove(old)
    transform.tag = tag
    parent.insert(0, transform)


def _rect_transform(bounds):
    x, y, width, height = bounds
    transform = ET.Element(A + "xfrm")
    ET.SubElement(transform, A + "off", x=str(x), y=str(y))
    ET.SubElement(transform, A + "ext", cx=str(width), cy=str(height))
    return transform


def _select_layout(layouts, source_type, has_title):
    preferred = ([source_type, "obj", "tx", "titleOnly", "blank"] if has_title else ["blank", "obj", "tx"])
    for kind in preferred:
        matching = [item for item in layouts if item[1].get("type") == kind]
        if matching:
            return matching[0]
    return layouts[0]


def _layout_name(layout):
    node = layout[1]
    return node.find(P + "cSld").get("name", node.get("type", "Layout"))


def _resolve_layout_overrides(layouts, slide_count, overrides):
    if not overrides:
        return {}
    resolved = {}
    for slide_number, layout_name in overrides.items():
        if not isinstance(slide_number, int) or not 1 <= slide_number <= slide_count:
            raise ValueError(f"Template layout override has invalid slide number {slide_number}.")
        matches = [layout for layout in layouts if _layout_name(layout) == layout_name]
        if not matches:
            raise ValueError(f"Template layout '{layout_name}' was not found.")
        if len(matches) > 1:
            raise ValueError(f"Template layout '{layout_name}' is ambiguous.")
        resolved[slide_number] = matches[0]
    return resolved


def _content_area(layout, master, width, height, has_title):
    candidates = []
    for shape in _tree(layout):
        if _role(shape) in {"body", "obj", "subTitle"}:
            try:
                candidates.append(_bounds(_resolved_transform(shape, layout, master)))
            except ValueError:
                continue
    candidates = [b for b in candidates if b[2] > 0 and b[3] > 0]
    if candidates:
        x1 = min(bounds[0] for bounds in candidates)
        y1 = min(bounds[1] for bounds in candidates)
        x2 = max(bounds[0] + bounds[2] for bounds in candidates)
        y2 = max(bounds[1] + bounds[3] for bounds in candidates)
        return x1, y1, x2 - x1, y2 - y1
    return (round(width * .05), round(height * (.20 if has_title else .08)),
            round(width * .90), round(height * (.70 if has_title else .84)))


def _restyle_slide(
    slide,
    source_layout,
    source_master,
    target_layout,
    target_master,
    source_width,
    source_height,
    width,
    height,
):
    # Shape animation timing depends on grouping and needs a dedicated converter.
    if slide.find(P + "timing") is not None:
        raise ValueError("Template replacement does not support animated source slides.")
    tree = _tree(slide)
    target_title = next((s for s in _tree(target_layout) if _role(s) in {"title", "ctrTitle"}), None)
    title_shape = next((s for s in tree if _role(s) in {"title", "ctrTitle"}), None)
    preserve_title = title_shape is not None and target_title is not None
    content = []
    for shape in list(tree):
        if shape.tag in {P + "nvGrpSpPr", P + "grpSpPr", P + "extLst"}:
            continue
        ph = _placeholder(shape)
        role = _role(shape)
        # The target template owns page numbering, while empty metadata
        # placeholders are only authoring prompts. Filled source headers,
        # footers and dates can contain citations or legal notices, so retain
        # them outside the reflowed content group at the same relative page
        # position.
        if ph is not None and role == "sldNum":
            tree.remove(shape)
            continue
        if ph is not None and role in {"dt", "date", "ftr", "footer", "hdr", "header"}:
            has_value = (
                any((text.text or "").strip() for text in shape.iter(A + "t"))
                or any(key.startswith("{" + R + "}") for node in shape.iter() for key in node.attrib)
            )
            if not has_value:
                tree.remove(shape)
                continue
            transform = _resolved_transform(shape, source_layout, source_master)
            x, y, shape_width, shape_height = _bounds(transform)
            scaled = deepcopy(transform)
            off, ext = scaled.find(A + "off"), scaled.find(A + "ext")
            off.set("x", str(round(x * width / source_width)))
            off.set("y", str(round(y * height / source_height)))
            ext.set("cx", str(round(shape_width * width / source_width)))
            ext.set("cy", str(round(shape_height * height / source_height)))
            _set_transform(shape, scaled)
            ph.getparent().remove(ph)
            continue
        # Empty placeholders are authoring prompts, not user content.
        if (shape.tag == P + "sp" and ph is not None
                and not any((t.text or "").strip() for t in shape.iter(A + "t"))
                and not any(k.startswith("{" + R + "}") for n in shape.iter() for k in n.attrib)
                and all(n.tag == A + "xfrm" for n in shape.find(P + "spPr"))):
            tree.remove(shape)
            continue
        transform = _resolved_transform(shape, source_layout, source_master)
        if preserve_title and shape is title_shape:
            target_transform = _resolved_transform(target_title, target_layout, target_master)
            _set_transform(shape, target_transform)
            ph.attrib.clear()
            ph.attrib.update(_placeholder(target_title).attrib)
            continue
        _set_transform(shape, transform)
        if ph is not None:
            ph.getparent().remove(ph)
        content.append((shape, _bounds(transform)))
    if content:
        x1 = min(b[0] for _, b in content)
        y1 = min(b[1] for _, b in content)
        x2 = max(b[0] + max(1, b[2]) for _, b in content)
        y2 = max(b[1] + max(1, b[3]) for _, b in content)
        bx, by, bw, bh = _content_area(target_layout, target_master, width, height, preserve_title)
        scale = min(bw / (x2 - x1), bh / (y2 - y1))
        # Do not enlarge small content beyond its original size just to fill space.
        scale = min(scale, 1.0)
        outw, outh = max(1, round((x2 - x1) * scale)), max(1, round((y2 - y1) * scale))
        ids = [int(n.get("id")) for n in slide.iter(P + "cNvPr")]
        group = ET.Element(P + "grpSp")
        nv = ET.SubElement(group, P + "nvGrpSpPr")
        ET.SubElement(nv, P + "cNvPr", id=str(max(ids, default=0) + 1), name="Template content")
        ET.SubElement(nv, P + "cNvGrpSpPr")
        ET.SubElement(nv, P + "nvPr")
        props = ET.SubElement(group, P + "grpSpPr")
        xfrm = _rect_transform((bx + (bw - outw) // 2, by + (bh - outh) // 2, outw, outh))
        ET.SubElement(xfrm, A + "chOff", x=str(x1), y=str(y1))
        ET.SubElement(xfrm, A + "chExt", cx=str(x2 - x1), cy=str(y2 - y1))
        props.append(xfrm)
        for shape, _ in content:
            group.append(shape)
        ext = tree.find(P + "extLst")
        tree.insert(tree.index(ext) if ext is not None else len(tree), group)
    common = slide.find(P + "cSld")
    background = common.find(P + "bg")
    if background is not None:
        common.remove(background)
    override = slide.find(P + "clrMapOvr")
    if override is not None:
        slide.remove(override)
    # Explicitly enable target master artwork even if the source hid its own.
    slide.set("showMasterSp", "1")


def _merged_package(source, template, layouts, layout_overrides=None):
    """Build a virtual OPC source; only selected dependencies reach final output."""
    blobs = {name: source.zip.read(name) for name in source.names}
    types = _parse(blobs["[Content_Types].xml"])
    prefix = "template/"
    counter = 1
    while any(name.startswith(prefix) for name in blobs):
        counter += 1
        prefix = f"template_{counter}/"
    for name in sorted(template.names):
        if name == "[Content_Types].xml" or name.endswith("/"):
            continue
        mapped = prefix + name
        if mapped in blobs:
            raise ValueError("Source package conflicts with the template namespace.")
        if name.endswith(".rels"):
            # Absolute and relative OPC targets must both enter the prefixed
            # template graph; raw absolute targets could resolve to source parts.
            if name == "_rels/.rels":
                part = ""
            else:
                parent, filename = posixpath.split(name)
                part = posixpath.join(posixpath.dirname(parent), filename[:-5])
            relations = _relations()
            for rid, (kind, target, external) in template.rels(part).items():
                _rel(relations, rid, kind, target if external else "/" + prefix + target, external)
            blobs[mapped] = _xml(relations)
        else:
            blobs[mapped] = template.zip.read(name)
            ET.SubElement(types, CT + "Override", PartName="/" + mapped,
                          ContentType=template.mime(name))
    root = _parse(blobs[PRES])
    source_width, source_height = _dims(root.find(P + "sldSz"))
    target_size = template.root.find(P + "sldSz")
    root.replace(root.find(P + "sldSz"), deepcopy(target_size))
    default = root.find(P + "defaultTextStyle")
    if default is not None:
        root.remove(default)
    target_default = template.root.find(P + "defaultTextStyle")
    if target_default is not None:
        root.append(deepcopy(target_default))
    # Merge embedded template font references into the presentation manifest.
    pres_rels = _parse(blobs[_rels_name(PRES)])
    fonts = template.root.find(P + "embeddedFontLst")
    if fonts is not None:
        dest_fonts = root.find(P + "embeddedFontLst")
        if dest_fonts is None:
            dest_fonts = ET.Element(P + "embeddedFontLst")
            root.insert(list(root).index(root.find(P + "notesSz")) + 1, dest_fonts)
        for entry in fonts:
            copied = deepcopy(entry)
            for node in copied:
                rid = node.get(RID)
                if rid:
                    kind, target, external = template.manifest[rid]
                    if external or kind != R + "/font":
                        raise ValueError("Invalid template font reference.")
                    new_rid = "rIdTemplateFont" + str(len(pres_rels) + 1)
                    _rel(pres_rels, new_rid, kind, "/" + prefix + target)
                    node.set(RID, new_rid)
            dest_fonts.append(copied)
    width, height = _dims(target_size)
    used = []
    for slide_number, part in enumerate(source.slides, 1):
        rels = source.rels(part)
        layout_links = [(rid, target) for rid, (kind, target, ext) in rels.items()
                        if kind == R + "/slideLayout" and not ext]
        if len(layout_links) != 1:
            raise ValueError("A source slide needs exactly one layout.")
        layout_rid, old_layout = layout_links[0]
        old_layout_node = _parse(source.zip.read(old_layout))
        masters = [target for kind, target, ext in source.rels(old_layout).values()
                   if kind == R + "/slideMaster" and not ext]
        if len(masters) != 1:
            raise ValueError("A source layout needs exactly one master.")
        old_master = _parse(source.zip.read(masters[0]))
        node = _parse(blobs[part])
        has_title = any(_role(s) in {"title", "ctrTitle"} for s in _tree(node))
        target, target_node, _, master_node = (layout_overrides or {}).get(
            slide_number,
            _select_layout(layouts, old_layout_node.get("type"), has_title),
        )
        _restyle_slide(
            node,
            old_layout_node,
            old_master,
            target_node,
            master_node,
            source_width,
            source_height,
            width,
            height,
        )
        new_rels = _relations()
        for rid, (kind, rel_target, external) in rels.items():
            _rel(new_rels, rid, kind,
                 "/" + prefix + target if rid == layout_rid else rel_target if external else "/" + rel_target,
                 external)
        blobs[part] = _xml(node)
        blobs[_rels_name(part)] = _xml(new_rels)
        used.append(_layout_name((target, target_node, None, master_node)))
    blobs[PRES] = _xml(root)
    blobs[_rels_name(PRES)] = _xml(pres_rels)
    blobs["[Content_Types].xml"] = _xml(types)
    result = io.BytesIO()
    with ZipFile(result, "w", compression=ZIP_DEFLATED) as archive:
        for name, data in blobs.items():
            archive.writestr(name, data)
    result.seek(0)
    return result, used


def apply_template(
    source: Path,
    template: Path,
    output: Path,
    layout_overrides: dict[int, str] | None = None,
) -> dict:
    """Apply a validated PPTX/POTX template, publishing a new PPTX atomically."""
    tmp = None
    try:
        source, template, output = Path(source), Path(template), Path(output)
        if output.resolve() in {source.resolve(), template.resolve()}:
            raise ValueError("Template output cannot replace an input file.")
        metadata = inspect_template(template)
        with ExitStack() as stack:
            original = _Source(stack.enter_context(ZipFile(source)))
            if not original.slides:
                raise ValueError("Select at least one slide for template replacement.")
            design = _open_template(stack, template)
            layouts = _layouts(design)
            overrides = _resolve_layout_overrides(layouts, len(original.slides), layout_overrides)
            merged_data, used = _merged_package(original, design, layouts, overrides)
            archive = stack.enter_context(ZipFile(merged_data))
            merged = _Source(archive)
            picks = [(merged, merged.select(i)) for i in range(1, len(merged.slides) + 1)]
            with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".template-", suffix=".pptx", delete=False) as f:
                tmp = Path(f.name)
            with ZipFile(tmp, "w", compression=ZIP_DEFLATED) as dest:
                draft = _Draft(dest)
                draft.finish(picks, [merged])
            os.replace(tmp, output)
            return {"slide_count": len(picks), "template": {**metadata, "appliedLayouts": used},
                    "warnings": sorted({*metadata["warnings"], *draft.warnings})}
    except (BadZipFile, ET.XMLSyntaxError, KeyError, TypeError, AttributeError,
            OSError, RuntimeError, EOFError) as exc:
        raise ValueError("Could not apply the PowerPoint template: unsupported or invalid package.") from exc
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
