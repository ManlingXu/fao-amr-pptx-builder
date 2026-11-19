"""Build an editable PPTX from the dependency graph of explicitly selected slides."""
from __future__ import annotations

import hashlib
import io
import os
import posixpath
import re
import tempfile
from collections import defaultdict
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

from lxml import etree as ET

P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
CT = "{http://schemas.openxmlformats.org/package/2006/content-types}"
REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
RID = "{" + R + "}id"
PRES = "ppt/presentation.xml"
MAIN = "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"
SLIDE = "application/vnd.openxmlformats-officedocument.presentationml.slide+xml"
XSHEET = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_PART = 128 * 1024**2
MAX_TOTAL = 512 * 1024**2

# Other selected-slide dependencies fail explicitly. A catch-all copy could import
# embedded decks, comments, custom XML, or active content into a shared draft.
NATIVE = {
    "slide", "slideLayout", "slideMaster", "notesSlide", "notesMaster", "theme",
    "themeOverride", "image", "chart", "chartStyle", "chartColorStyle", "package",
    "diagramData", "diagramLayout", "diagramQuickStyle", "diagramColors", "diagramDrawing",
    "audio", "video", "media", "font", "hyperlink",
}


def _parse(blob):
    parser = ET.XMLParser(resolve_entities=False, load_dtd=False, no_network=True, huge_tree=False)
    node = ET.fromstring(blob, parser)
    if node.getroottree().docinfo.doctype:
        raise ValueError("DTDs are unsupported in Office XML.")
    return node


def _xml(node):
    return ET.tostring(node, encoding="UTF-8", xml_declaration=True, standalone=True)


def _rels_name(part):
    directory, name = posixpath.split(part)
    return posixpath.join(directory, "_rels", name + ".rels")


def _check_zip(z):
    entries, seen, total = z.infolist(), set(), 0
    if len(entries) > 20000:
        raise ValueError("Office ZIP contains too many entries.")
    for item in entries:
        name = item.filename.rstrip("/")
        components = name.split("/")
        if (any(c in ("", ".", "..") for c in components) or "\\" in name or ":" in name
                or "%" in unquote(name) or any(c in (".", "..") for c in unquote(name).split("/"))
                or any(ord(c) < 32 for c in name) or name.casefold() in seen):
            raise ValueError("Invalid or duplicate Office ZIP part path.")
        seen.add(name.casefold())
        if item.flag_bits & 1:
            raise ValueError("Encrypted Office packages are unsupported.")
        if any(token in name.casefold() for token in ("vbaproject", "activex/", "vbadata", "macrosheets/")):
            raise ValueError("Macro-enabled or active Office content is unsupported.")
        total += item.file_size
        if item.file_size > MAX_PART or total > MAX_TOTAL:
            raise ValueError("Office package exceeds supported uncompressed size.")
    types = _parse(z.read("[Content_Types].xml"))
    if types.tag != CT + "Types":
        raise ValueError("Invalid Office content type manifest.")
    if any(any(word in e.get("ContentType", "").lower() for word in ("macroenabled", "vba", "activex"))
           for e in types):
        raise ValueError("Macro-enabled or active Office content is unsupported.")
    return types


def _resolve(part, target, names):
    uri = urlsplit(target)
    decoded = unquote(uri.path)
    if (uri.scheme or uri.netloc or uri.query or uri.fragment or not decoded
            or "\\" in decoded or ":" in decoded or any(ord(c) < 32 for c in decoded)):
        raise ValueError("Unsupported internal Office relationship URI.")
    name = (posixpath.normpath(decoded[1:]) if decoded.startswith("/") else
            posixpath.normpath(posixpath.join(posixpath.dirname(part), decoded)))
    if name.startswith("../") or name not in names:
        raise ValueError("Office relationship resolves outside the package or to a missing part.")
    return name


def _read_rels(z, names, part):
    name = _rels_name(part)
    if name not in names:
        return {}
    node = _parse(z.read(name))
    if node.tag != REL+"Relationships":
        raise ValueError("Invalid relationship file.")
    result = {}
    for rel in node:
        rid, kind, target = (rel.attrib[key] for key in ("Id", "Type", "Target"))
        if rid in result or rel.tag != REL+"Relationship" or not rid:
            raise ValueError("Invalid or duplicate Office relationship.")
        mode = rel.get("TargetMode", "Internal")
        if mode not in {"Internal", "External"}:
            raise ValueError("Invalid relationship target mode.")
        external = mode == "External"
        result[rid] = kind, target if external else _resolve(part, target, names), external
    return result


def _validate_workbook(z):
    """Accept self-contained worksheet data only. The whole embedded ZIP is copied."""
    types = _check_zip(z)
    names = {item.filename for item in z.infolist() if not item.is_dir()}
    overrides = {unquote(n.attrib["PartName"]).lstrip("/"): n.attrib["ContentType"]
                 for n in types if n.tag == CT+"Override"}
    defaults = {n.attrib["Extension"].lower(): n.attrib["ContentType"]
                for n in types if n.tag == CT+"Default"}
    office = "application/vnd.openxmlformats-officedocument."
    sheet = office + "spreadsheetml."
    core = "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties"
    allowed = {
        R+"/officeDocument": XSHEET+".main+xml",
        R+"/worksheet": sheet+"worksheet+xml",
        R+"/styles": sheet+"styles+xml",
        R+"/sharedStrings": sheet+"sharedStrings+xml",
        R+"/table": sheet+"table+xml",
        R+"/calcChain": sheet+"calcChain+xml",
        R+"/theme": office+"theme+xml",
        R+"/extended-properties": office+"extended-properties+xml",
        R+"/custom-properties": office+"custom-properties+xml",
        core: "application/vnd.openxmlformats-package.core-properties+xml",
    }
    forbidden = {"externalReference", "externalBook", "ddeLink", "oleLink", "oleObject",
                 "connections", "queryTable", "webPublishObject"}
    pending = [""]
    processed = set()
    retained = {"[Content_Types].xml"}
    while pending:
        part = pending.pop()
        if part in processed:
            continue
        processed.add(part)
        rels = _read_rels(z, names, part)
        relfile = _rels_name(part)
        if relfile in names:
            retained.add(relfile)
        if not part:
            main = [t for k, t, ext in rels.values() if k == R+"/officeDocument" and not ext]
            if main != ["xl/workbook.xml"]:
                raise ValueError("Expected a standard embedded XLSX workbook.")
        else:
            retained.add(part)
            node = _parse(z.read(part))
            for el in node.iter():
                if not isinstance(el.tag, str):
                    continue
                if ET.QName(el).localname in forbidden:
                    raise ValueError("External data and embedded objects in chart workbooks are unsupported.")
                for key, value in el.attrib.items():
                    if key.startswith("{"+R+"}") and value and value not in rels:
                        raise ValueError("An embedded worksheet part references a missing relationship.")
        for kind, target, external in rels.values():
            if external or kind not in allowed:
                raise ValueError("External links, connections and attachments in chart workbooks are unsupported.")
            ext = target.rsplit(".", 1)[-1].lower()
            if overrides.get(target, defaults.get(ext)) != allowed[kind]:
                raise ValueError("Embedded workbook relationship has an incompatible part type.")
            pending.append(target)
    if retained != names:
        raise ValueError("Embedded chart workbook contains an unsupported unreferenced part.")


def _relations():
    return ET.Element(REL + "Relationships", nsmap={None: REL[1:-1]})


def _rel(root, rid, kind, target, external=False):
    node = ET.SubElement(root, REL + "Relationship", Id=rid, Type=kind, Target=target)
    if external:
        node.set("TargetMode", "External")


def _dims(node):
    if node is None:
        raise ValueError("Presentation is missing its slide or notes dimensions.")
    result = tuple(int(node.attrib[k]) for k in ("cx", "cy"))
    if min(result) <= 0:
        raise ValueError("Invalid PowerPoint page dimensions.")
    return result


class _Source:
    def __init__(self, z):
        self.zip = z
        self.names = set(z.namelist())
        types = _check_zip(z)
        self.defaults = {n.get("Extension", "").lower(): n.get("ContentType") for n in types if n.tag == CT+"Default"}
        self.overrides = {unquote(n.get("PartName", "")).lstrip("/"): n.get("ContentType")
                          for n in types if n.tag == CT+"Override"}
        documents = [target for kind, target, external in self.rels("").values()
                     if kind == R+"/officeDocument" and not external]
        if documents != [PRES] or self.mime(PRES) != MAIN:
            raise ValueError("Expected a standard .pptx presentation.")
        self.root = _parse(z.read(PRES))
        if self.root.tag != P+"presentation":
            raise ValueError("Only transitional PowerPoint OOXML is supported.")
        self.manifest = self.rels(PRES)
        self.slides = []
        for entry in self.root.findall(P+"sldIdLst/"+P+"sldId"):
            kind, target, external = self.manifest[entry.attrib[RID]]
            if external or kind != R+"/slide" or self.mime(target) != SLIDE:
                raise ValueError("Invalid source slide relationship.")
            self.slides.append(target)
        self.selected = set()
        self.layouts = set()
        self.faces = set()
        self.table_ids = set()
        self.default_table = False
        self.graph_hashes = {}

    def mime(self, name):
        mime = self.overrides.get(name) or self.defaults.get(name.rsplit(".", 1)[-1].lower())
        if not mime:
            raise ValueError("Office part is missing its content type.")
        return mime

    def rels(self, part):
        return _read_rels(self.zip, self.names, part)

    def select(self, number):
        if type(number) is not int or not 1 <= number <= len(self.slides):
            raise ValueError("Slide number must be a valid 1-based integer.")
        name = self.slides[number-1]
        if name in self.selected:
            raise ValueError("Duplicate slide selection.")
        self.selected.add(name)
        layouts = [t for k, t, ext in self.rels(name).values() if k == R+"/slideLayout" and not ext]
        if len(layouts) != 1:
            raise ValueError("A selected slide needs exactly one layout.")
        self.layouts.update(layouts)
        return name

    def dependency_hash(self, part, path=()):
        """Notes masters are presentation-wide. Coalesce only identical source graphs."""
        if part not in self.graph_hashes:
            if part in path or len(path) > 32:
                raise ValueError("Unexpected cycle in notes master dependencies.")
            h = hashlib.sha256(self.zip.read(part))
            for rid, (kind, target, external) in sorted(self.rels(part).items()):
                h.update(repr((rid, kind, external)).encode())
                h.update(target.encode() if external else self.dependency_hash(target, (*path, part)))
            self.graph_hashes[part] = h.digest()
        return self.graph_hashes[part]

    def collect_styles(self, root):
        self.faces.update(n.get("typeface").casefold() for n in root.iter() if n.get("typeface"))
        for table in root.iter(A+"tbl"):
            style = table.find(A+"tblPr/"+A+"tableStyleId")
            if style is not None and style.text:
                self.table_ids.add(style.text)
            else:
                self.default_table = True


class _Draft:
    def __init__(self, archive):
        self.z = archive
        self.types = ET.Element(CT+"Types", nsmap={None: CT[1:-1]})
        ET.SubElement(self.types, CT+"Default", Extension="rels",
                      ContentType="application/vnd.openxmlformats-package.relationships+xml")
        self.parts = {}
        self.taken = {PRES}
        self.counts = defaultdict(int)
        self.masters = []
        self.notes = None
        self.notes_hash = None
        self.next_master_id = 2147483648
        self.warnings = set()
        self.total = 0
        self.root_rels = _relations()

    def write(self, name, data, mime=None):
        self.total += len(data)
        if self.total > MAX_TOTAL:
            raise ValueError("Draft exceeds the supported uncompressed size.")
        self.z.writestr(name, data)
        if mime:
            ET.SubElement(self.types, CT+"Override", PartName="/" + quote(name, safe="/"), ContentType=mime)

    def allocate(self, old):
        prefix, ext = posixpath.splitext(old)
        stem = re.sub(r"[0-9]+$", "", prefix)
        while True:
            self.counts[stem, ext] += 1
            candidate = f"{stem}{self.counts[stem, ext]}{ext}"
            if candidate not in self.taken:
                self.taken.add(candidate)
                return candidate

    def global_rel(self, kind, part):
        rid = f"rId{len(self.root_rels)+1}"
        _rel(self.root_rels, rid, R+"/"+kind, quote(posixpath.relpath(part, "ppt"), safe="/"))
        return rid

    def master_id(self):
        value = self.next_master_id
        self.next_master_id += 1
        return str(value)

    def copy(self, source, part, depth=0):
        if (source, part) in self.parts:
            return self.parts[source, part]
        if depth > 48:
            raise ValueError("Office part dependencies are too deeply nested.")
        mime = source.mime(part)
        if mime == SLIDE and part not in source.selected:
            raise ValueError("An unexpected dependency references an unselected slide.")
        if mime.endswith("notesMaster+xml"):
            digest = source.dependency_hash(part)
            if self.notes:
                if digest != self.notes_hash:
                    raise ValueError("Different notes master designs cannot be combined without changing notes formatting.")
                self.parts[source, part] = self.notes
                return self.notes
            self.notes_hash = digest
        dest = self.parts[source, part] = self.allocate(part)
        if mime.endswith("slideMaster+xml"):
            self.masters.append(dest)
        if mime.endswith("notesMaster+xml"):
            self.notes = dest
        raw = source.zip.read(part)
        is_xml = mime.endswith("+xml") or mime.endswith("/xml") or part.endswith((".xml", ".svg"))
        node = _parse(raw) if is_xml else None
        changed = False
        if node is not None:
            source.collect_styles(node)
        rels = _relations()
        for rid, (kind, target, external) in source.rels(part).items():
            short = kind.rsplit("/", 1)[-1]
            if short not in NATIVE:
                raise ValueError(f"Unsupported selected-slide dependency: {short}.")
            if external:
                if short != "hyperlink" or urlsplit(target).scheme.lower() not in {"http", "https", "mailto"}:
                    raise ValueError("Linked media, external data and non-web hyperlink targets are unsupported.")
                _rel(rels, rid, kind, target, True)
                continue
            target_mime = source.mime(target)
            if short == "image" and not target_mime.startswith("image/"):
                raise ValueError("Image relationship has an incompatible target content type.")
            if short in {"slide", "slideLayout", "slideMaster", "notesSlide", "notesMaster"}:
                if target_mime != f"application/vnd.openxmlformats-officedocument.presentationml.{short}+xml":
                    raise ValueError(f"{short} relationship has an incompatible target content type.")
            if short == "slideLayout" and mime.endswith("slideMaster+xml") and target not in source.layouts:
                for entry in node.findall(P+"sldLayoutIdLst/"+P+"sldLayoutId"):
                    if entry.get(RID) == rid:
                        entry.getparent().remove(entry)
                        changed = True
                continue
            if (short == "slide" or source.mime(target) == SLIDE) and target not in source.selected:
                references = [e for e in node.iter() if rid in e.attrib.values()] if node is not None else []
                if any(e.tag not in {A+"hlinkClick", A+"hlinkHover", A+"hlinkMouseOver"} for e in references):
                    raise ValueError("An unsupported object links to an unselected slide.")
                if mime.endswith("notesSlide+xml"):
                    raise ValueError("A notes page points to an unexpected slide.")
                for ref in references:
                    ref.getparent().remove(ref)
                self.warnings.add("Removed a link to a slide outside the selection.")
                changed |= bool(references)
                continue
            if short == "package":
                if not mime.endswith("drawingml.chart+xml") or source.mime(target) != XSHEET:
                    raise ValueError("Only embedded XLSX chart workbooks are supported as attached packages.")
                with ZipFile(io.BytesIO(source.zip.read(target))) as workbook:
                    _validate_workbook(workbook)
            dependency = self.copy(source, target, depth+1)
            rel_target = posixpath.relpath(dependency, posixpath.dirname(dest))
            _rel(rels, rid, kind, quote(rel_target, safe="/"))
        if node is not None:
            if node.tag == P+"sldMaster":
                for layout in node.findall(P+"sldLayoutIdLst/"+P+"sldLayoutId"):
                    layout.set("id", self.master_id())
                changed = True
            valid_ids = {entry.get("Id") for entry in rels}
            for element in node.iter():
                for key, value in element.attrib.items():
                    if key.startswith("{"+R+"}") and value and value not in valid_ids:
                        raise ValueError("An XML element references a missing relationship.")
        self.write(dest, _xml(node) if changed else raw, mime)
        if len(rels):
            self.write(_rels_name(dest), _xml(rels))
        return dest

    def embed_fonts(self, sources, root):
        fonts = ET.Element(P+"embeddedFontLst")
        faces = {}
        for source in sources:
            for entry in source.root.findall(P+"embeddedFontLst/"+P+"embeddedFont"):
                descriptor = entry.find(P+"font")
                face = descriptor.attrib["typeface"].casefold()
                if face not in source.faces:
                    continue
                if face not in faces:
                    group = ET.SubElement(fonts, P+"embeddedFont")
                    group.append(deepcopy(descriptor))
                    faces[face] = group, {}
                group, variants = faces[face]
                for variant in entry:
                    if variant.tag == P+"font":
                        continue
                    kind, target, external = source.manifest[variant.attrib[RID]]
                    if external or kind != R+"/font":
                        raise ValueError("Invalid embedded font relationship.")
                    digest = hashlib.sha256(source.zip.read(target)).digest()
                    if variant.tag in variants:
                        if variants[variant.tag] != digest:
                            raise ValueError("Source files contain conflicting embedded fonts with the same face and style.")
                        continue
                    variants[variant.tag] = digest
                    el = deepcopy(variant)
                    el.set(RID, self.global_rel("font", self.copy(source, target)))
                    group.append(el)
        if len(fonts):
            order = {P+k: i for i, k in enumerate(("font", "regular", "bold", "italic", "boldItalic"))}
            for group in fonts:
                group[:] = sorted(group, key=lambda n: order[n.tag])
            root.set("embedTrueTypeFonts", "1")
            root.append(fonts)

    def table_styles(self, sources):
        table = None
        styles = {}
        default = None
        for source in sources:
            if not source.table_ids and not source.default_table:
                continue
            for kind, target, ext in source.manifest.values():
                if kind != R+"/tableStyles" or ext:
                    continue
                node = _parse(source.zip.read(target))
                if source.rels(target):
                    raise ValueError("Custom table styles with external part dependencies are unsupported.")
                if table is None:
                    table = ET.Element(A+"tblStyleLst", nsmap={"a": A[1:-1]}, attrib=dict(node.attrib))
                used = set(source.table_ids)
                if source.default_table:
                    current = node.attrib["def"]
                    if default is not None and default != current:
                        raise ValueError("Selected tables use incompatible presentation-wide default styles.")
                    default = current
                    used.add(current)
                for style in node:
                    key = style.get("styleId")
                    if key not in used:
                        continue
                    signature = ET.tostring(style, method="c14n", exclusive=True)
                    if key in styles and styles[key] != signature:
                        raise ValueError("Conflicting custom table style definitions.")
                    if key not in styles:
                        table.append(deepcopy(style))
                        source.collect_styles(style)
                        styles[key] = signature
        if table is not None:
            if default:
                table.set("def", default)
            self.global_rel("tableStyles", "ppt/tableStyles.xml")
            self.write("ppt/tableStyles.xml", _xml(table),
                       "application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml")

    def finish(self, picks, sources):
        first = picks[0][0].root
        root = ET.Element(P+"presentation", nsmap={"p": P[1:-1], "a": A[1:-1], "r": R})
        for attr in ("saveSubsetFonts", "autoCompressPictures", "strictFirstAndLastChars"):
            if attr in first.attrib:
                root.set(attr, first.attrib[attr])
        for source, part in picks:
            self.copy(source, part)
        masters = ET.SubElement(root, P+"sldMasterIdLst")
        for name in self.masters:
            ET.SubElement(masters, P+"sldMasterId", id=self.master_id(),
                          attrib={RID: self.global_rel("slideMaster", name)})
        if self.notes:
            notes = ET.SubElement(root, P+"notesMasterIdLst")
            ET.SubElement(notes, P+"notesMasterId", {RID: self.global_rel("notesMaster", self.notes)})
        slides = ET.SubElement(root, P+"sldIdLst")
        for index, pair in enumerate(picks, 256):
            ET.SubElement(slides, P+"sldId", id=str(index), attrib={RID: self.global_rel("slide", self.parts[pair])})
        for tag in ("sldSz", "notesSz"):
            root.append(deepcopy(first.find(P+tag)))
        self.table_styles(sources)
        default = first.find(P+"defaultTextStyle")
        for source in sources:
            style = source.root.find(P+"defaultTextStyle")
            if style is not None:
                source.collect_styles(style)
            if _style_key(style) != _style_key(default):
                raise ValueError("Incompatible presentation-wide default text styles.")
        self.embed_fonts(sources, root)
        if default is not None:
            root.append(deepcopy(default))
        self.write(PRES, _xml(root), MAIN)
        self.write(_rels_name(PRES), _xml(self.root_rels))
        package = _relations()
        _rel(package, "rId1", R+"/officeDocument", PRES)
        self.write("_rels/.rels", _xml(package))
        self.write("[Content_Types].xml", _xml(self.types))


def _style_key(node):
    if node is None:
        return None
    return ET.tostring(node, method="c14n", exclusive=True)


def assemble_slides(selections: list[tuple[Path, int]], output_path: Path) -> dict:
    """Copy 1-based source slides in request order. Publish the file atomically."""
    if not selections:
        raise ValueError("Select at least one slide.")
    tmp = None
    try:
        output = Path(output_path)
        with ExitStack() as stack:
            sources = {}
            picks = []
            canvas = None
            for path, number in selections:
                path = Path(path).resolve()
                if path == output.resolve():
                    raise ValueError("Draft destination cannot replace a source presentation.")
                if path.suffix.lower() != ".pptx":
                    raise ValueError("Only .pptx input is supported. Macro-enabled and legacy PowerPoint files are unsupported.")
                if path not in sources:
                    file = stack.enter_context(path.open("rb"))
                    if file.read(8) == bytes.fromhex("d0cf11e0a1b11ae1"):
                        raise ValueError("Encrypted or legacy binary PowerPoint input is unsupported.")
                    source = sources[path] = _Source(stack.enter_context(ZipFile(file)))
                    dims = tuple(_dims(source.root.find(P+tag)) for tag in ("sldSz", "notesSz"))
                    if canvas and dims != canvas:
                        raise ValueError("Source slide or notes canvas dimensions differ.")
                    canvas = dims
                source = sources[path]
                picks.append((source, source.select(number)))
            with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".draft-", suffix=".pptx", delete=False) as f:
                tmp = Path(f.name)
            with ZipFile(tmp, "w", compression=ZIP_DEFLATED) as archive:
                draft = _Draft(archive)
                draft.finish(picks, sources.values())
            os.replace(tmp, output)
            return {"slide_count": len(picks), "warnings": sorted(draft.warnings)}
    except (BadZipFile, ET.XMLSyntaxError, KeyError, TypeError, AttributeError, NotImplementedError,
            RuntimeError, EOFError, OSError) as exc:
        raise ValueError(f"Could not assemble the PowerPoint package: {exc}") from exc
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
