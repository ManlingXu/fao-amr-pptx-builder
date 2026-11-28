"""Incremental index and evidence-grounded retrieval for a local AMR briefing."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Sequence
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from urllib.parse import urlsplit
from zipfile import BadZipFile

from pptx.exc import PackageNotFoundError

from .pptx_parser import parse_presentation
from .providers.base import MAX_FILE_BYTES, MAX_LIBRARY_FILES


# Controlled concepts supplement exact words, which remain useful for named programmes,
# species, figures and topics outside the vocabulary. Geography denotes slide subject,
# not where an international workshop happened to take place.
CONCEPTS = {
    "amr": "amr|antimicrobial resistance|antibiotic resistance|resistant|resistance|耐药性|耐药|抗药性",
    "antibiotic": "antibiotic|antibiotics|antimicrobial|antimicrobials|抗微生物药物|抗菌药物|抗生素|抗菌药",
    "stewardship": "stewardship|ams|prudent|responsible use|rational use|appropriate use|judicious use|合理使用|合理用药|审慎用药|用药管理|审慎使用",
    "use": "amu|amc|consumption|antimicrobial use|antibiotic use|用量|使用量|消耗量",
    "animal": "animal|animals|veterinary|veterinarian|veterinarians|livestock|farm animals|farmed animals|food-producing animals|兽医|兽用|动物|畜牧|畜禽|养殖",
    "poultry": "poultry|chicken|chickens|broiler|broilers|flock|家禽|养鸡|肉鸡|鸡群",
    "pigs": "pig|pigs|porcine|swine|piglets|生猪|养猪|猪",
    "cattle": "cattle|bovine|dairy|dairy cows|cow|cows|奶牛|肉牛|牛群|乳牛",
    "aquaculture": "aquaculture|farmed fish|fish|水产|鱼类|养鱼",
    "human": "human health|hospital|hospitals|clinical wards|hospitalised|医院|人医|人类健康|住院",
    "onehealth": "one health|one-health|multisectoral|同一健康|一个健康|跨部门",
    "farmers": "farmer|farmers|smallholder|smallholders|farmers'|农户|养殖户|农民",
    "leaders": "traditional leaders|civic leaders|community leaders|traditional chiefs|传统领袖|社区领袖|传统领导",
    "awareness": "awareness|outreach|radio|sensitization|sensitisation|engagement|campaign|reach|宣传|广播|提高意识|外展",
    "training": "training|trainings|trained|education|mentorship|workshop|培训|教育|能力建设",
    "policy": "policy|policies|action plan|action plans|national plan|legislation|regulation|regulations|guidelines|legislative|政策|行动计划|立法|法规|指南",
    "surveillance": "surveillance|monitor|monitoring|tracking|监测|监控",
    "sales": "sale|sales|sold|销售量|销量|销售",
    "mg/kg": "mg/kg|mg per kg|毫克/千克|毫克每千克",
    "population-adjusted": "adjusted for animal population|animal population|动物群体规模|动物群体数量|动物总量",
    "trends": "trend|trends|trending|趋势|变化趋势",
    "reduction": "reduce|reducing|reduction|decrease|target|targets|lower|exposure|减量|减少|降低|暴露|目标",
    "prevention": "biosecurity|prevention|vaccination|vaccinations|infection control|预防|防控|生物安全|免疫",
    "laboratory": "laboratory|laboratories|lab|实验室",
    "prescribing": "prescribing|prescription|prescriptions|audit|处方|审计",
    "environment": "environment|environmental|wastewater|环境|废水",
    "herd": "herd|herds|herd health|畜群|牛群健康",
    "food": "food safety|food chain|food system|food systems|食品安全|食物系统|食品链",
}
COUNTRIES = {
    "zambia": "zambia|zambian|zambias|赞比亚", "uk": "united kingdom|uk|british|england|英国",
    "france": "france|french|法国", "czechia": "czech|czechia|czech republic|捷克",
    "india": "india|indian|印度", "vietnam": "vietnam|viet nam|vietnamese|越南",
    "italy": "italy|italian|意大利", "china": "china|chinese|中国",
    "usa": "united states|united states of america|usa|u.s.|美国",
    "kenya": "kenya|kenyan|肯尼亚", "ghana": "ghana|ghanaian|加纳",
    "uganda": "uganda|ugandan|乌干达", "ethiopia": "ethiopia|ethiopian|埃塞俄比亚",
    "senegal": "senegal|senegalese|塞内加尔", "nigeria": "nigeria|nigerian|尼日利亚",
    "sweden": "sweden|swedish|瑞典", "latvia": "latvia|latvian|拉脱维亚",
    "ireland": "ireland|irish|爱尔兰", "portugal": "portugal|portuguese|葡萄牙",
    "germany": "germany|german|德国", "poland": "poland|polish|波兰",
    "austria": "austria|austrian|奥地利", "greece": "greece|greek|希腊",
    "cyprus": "cyprus|cypriot|塞浦路斯", "switzerland": "switzerland|swiss|瑞士",
    "spain": "spain|spanish|西班牙", "netherlands": "netherlands|dutch|荷兰",
    "denmark": "denmark|danish|丹麦", "norway": "norway|norwegian|挪威",
    "belgium": "belgium|belgian|比利时", "finland": "finland|finnish|芬兰",
    "romania": "romania|romanian|罗马尼亚", "hungary": "hungary|hungarian|匈牙利",
    "slovakia": "slovakia|slovak|斯洛伐克", "slovenia": "slovenia|slovenian|斯洛文尼亚",
    "croatia": "croatia|croatian|克罗地亚", "bulgaria": "bulgaria|bulgarian|保加利亚",
    "lithuania": "lithuania|lithuanian|立陶宛", "estonia": "estonia|estonian|爱沙尼亚",
    "australia": "australia|australian|澳大利亚", "canada": "canada|canadian|加拿大",
    "brazil": "brazil|brazilian|巴西", "indonesia": "indonesia|indonesian|印度尼西亚|印尼",
    "thailand": "thailand|thai|泰国", "pakistan": "pakistan|pakistani|巴基斯坦",
    "bangladesh": "bangladesh|bangladeshi|孟加拉国", "nepal": "nepal|nepalese|尼泊尔",
    "malawi": "malawi|malawian|马拉维", "tanzania": "tanzania|tanzanian|坦桑尼亚",
    "southafrica": "south africa|south african|南非", "japan": "japan|japanese|日本",
    "mexico": "mexico|mexican|墨西哥", "argentina": "argentina|argentinian|阿根廷",
    "peru": "peru|peruvian|秘鲁", "colombia": "colombia|colombian|哥伦比亚",
    "burkinafaso": "burkina faso|burkinabe|布基纳法索", "egypt": "egypt|egyptian|埃及",
    "morocco": "morocco|moroccan|摩洛哥", "cameroon": "cameroon|cameroonian|喀麦隆",
    "rwanda": "rwanda|rwandan|卢旺达", "zimbabwe": "zimbabwe|zimbabwean|津巴布韦",
    "sierra leone": "sierra leone|塞拉利昂", "liberia": "liberia|liberian|利比里亚",
    "newzealand": "new zealand|新西兰", "philippines": "philippines|filipino|菲律宾",
    "malaysia": "malaysia|malaysian|马来西亚", "cambodia": "cambodia|cambodian|柬埔寨",
}
STOP = set("""a an and or is of in to the for from at through by on as about
    presentation presentations ppt slides slide briefing brief overview report show find
    what which how did can with in into me please make create prepare explain give
    its an this has were was are have be their it that these those as other
    related support information session read introduction use used using any all
    summarize summarise outlines tell could would audience include latest
    work works part regarding actions practices preparing local key initial set""".split())
WIDE = {"amr", "antibiotic", "animal", "stewardship", "use", "onehealth", "human"}
SPECIES = {"poultry", "pigs", "cattle", "aquaculture"}
STAGES = ("Context", "Policy", "Implementation", "Monitoring", "Next steps")


def _normalize(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold())
                   if not unicodedata.combining(c)).replace("’", "'")


def _aliases(groups):
    aliases = {alias: key for key, values in groups.items() for alias in values.split("|")}
    # English aliases must match whole lexical tokens, while Chinese aliases may
    # occur inside unsegmented Chinese input.
    ordered = sorted(aliases, key=lambda s: (-len(s), s))
    english = "|".join(re.escape(a) for a in ordered if a.isascii())
    chinese = "|".join(re.escape(a) for a in ordered if not a.isascii())
    return aliases, re.compile(r"(?<![a-z0-9])(?:" + english + r")(?![a-z0-9])|" + chinese)


VOCAB, TERM_RE = _aliases(CONCEPTS)
GEO, GEO_RE = _aliases(COUNTRIES)
WORD_RE = re.compile(r"[a-z0-9]+")


def _matches(text, mapping, pattern):
    return {mapping[m.group()] for m in pattern.finditer(text)}


def _words(text):
    return {w for w in WORD_RE.findall(text) if w not in STOP and len(w) > 1}


@dataclass
class Features:
    words: set
    concepts: set
    places: set

    @classmethod
    def of(cls, text):
        text = _normalize(text)
        return cls(_words(text), _matches(text, VOCAB, TERM_RE), _matches(text, GEO, GEO_RE))


def _stage(title, body, concepts):
    title = _normalize(title)
    if re.search(r"next steps|way forward|recommendations|priorities", title):
        return "Next steps"
    if re.search(r"introduction|background|why |what is|overview|definition", title):
        return "Context"
    for terms in (Features.of(title).concepts, Features.of(body[:240]).concepts, concepts):
        if terms & {"policy", "onehealth"}:
            return "Policy"
        if terms & {"surveillance", "sales", "trends", "laboratory"}:
            return "Monitoring"
        if terms & {"training", "awareness", "prevention", "farmers", "prescribing"}:
            return "Implementation"
    return "Context"


def _annual_subject(page):
    # Many chart slides have no authored title. Read the opening text for their
    # subject, and distinguish population-adjusted sales from absolute tonnage.
    heading = _normalize(page.get("title", ""))
    text = _normalize(page.get("body", "")[:700])
    for passage in (heading, text):
        if re.search(r"\b(sales?|sold)\b|销售", passage):
            if re.search(r"mg\s*/\s*(kg|pcu)|per (kg|pcu)|population.adjusted", text):
                return 0
            if re.search(r"\btonnes?\b|\btonnage\b|吨", text):
                return 1
            return 2
        if re.search(r"clinical surveillance|diagnostic samples|临床监测", passage):
            return 4
        if re.search(r"antibiotic use|antimicrobial use|consumption|消耗量", passage):
            return 3
        if re.search(r"resistance|surveillance|耐药性|监测", passage):
            return 5
    return 6


def order_story(candidates: Sequence[dict]) -> list[dict]:
    """Use authored order in one deck, or narrative and reporting order across decks."""
    if len({c["deck_id"] for c in candidates}) <= 1:
        return sorted(candidates, key=lambda c: c["slide_number"])
    series = {c.get("series") for c in candidates}
    if len(series) == 1 and all(series):
        # Publication date can lag the reporting period. A unique year in the
        # source title identifies the edition; ambiguous or absent years cannot.
        years = {c["deck_id"]: set(re.findall(r"\b(?:19|20)\d\d\b", c.get("deck_title", "")))
                 for c in candidates}
        if all(len(values) == 1 for values in years.values()):
            editions = {deck: next(iter(values)) for deck, values in years.items()}
            if len(set(editions.values())) > 1:
                return sorted(candidates, key=lambda c: (STAGES.index(c["stage"]), _annual_subject(c),
                                                         editions[c["deck_id"]], c["slide_number"], c["deck_id"]))
    return sorted(candidates, key=lambda c: (STAGES.index(c["stage"]), -c["score"],
                                             c["deck_id"], c["slide_number"]))


def _passages(text, max_length=360):
    """Contiguous note/sentence/bullet passages whose English words stay intact."""
    spans = []
    for row in re.finditer(r"[^\n\v\r]+", text):
        # Periods following single initials (E. coli), citations or decimals
        # are frequent in public-health decks. Cut at a clear sentence end.
        for sentence in re.finditer(r".+?(?:(?<=[a-z]{3})\.(?=\s+[A-Z])|[!?。！？](?=\s|$)|$)", row.group()):
            words = list(re.finditer(r"\S+", sentence.group()))
            offset = row.start() + sentence.start()
            i = 0
            while i < len(words):
                end = i + 1
                while end < len(words) and words[end].end() - words[i].start() <= max_length:
                    end += 1
                start_at, end_at = offset + words[i].start(), offset + words[end - 1].end()
                if end_at - start_at <= max_length:
                    spans.append((start_at, end_at, i == 0))
                i = end
    for i, (left, right, is_opening) in enumerate(spans):
        if not is_opening:
            continue
        yield text[left:right]
        for j in range(i + 1, min(i + 8, len(spans))):
            if spans[j][1] - left > max_length:
                break
            right = spans[j][1]
        if right != spans[i][1]:
            yield text[left:right]


def _evidence(page, question):
    best = (-1.0, "", "")
    body = page["body"].removeprefix(page["title"]).strip() if page["title"] else page["body"]
    # Title-only picture pages still have a citable caption. When substantive
    # content exists, prefer a passage explaining the heading.
    notes = page["notes"]
    if re.fullmatch(r"(?:read (?:the )?presentation outline for the session|welcome participants to the session|read aloud the session title)[.\s]*", notes.strip(), re.I):
        notes = ""
    fields = [("body", body), ("notes", notes)]
    if not any(len(v.strip()) >= 4 and not v.strip().isdigit() for _, v in fields):
        fields.append(("title", page["title"]))
    for field, text in fields:
        for excerpt in _passages(text):
            excerpt = re.sub(r"\s+\d{1,3}$", "", excerpt).rstrip()
            if len(excerpt) < 4 or excerpt.isdigit():
                continue
            if (re.match(r"^(?:\d{1,4}\s*\n|et al\b|(?:photo )?credits?\b|source\s*:|reference\b|copyright\b)", excerpt, re.I)
                    or re.search(r"https?://|\bdoi:", excerpt, re.I)):
                continue
            f = Features.of(excerpt)
            score = (3 * len(question.concepts & f.concepts) + len(question.words & f.words)
                     + len(question.places & f.places) + min(len(excerpt), 100) / 140
                     + .2 * min(5, len(f.concepts)) + (1 if field == "body" else 0))
            if re.search(r"et al\.,? \d{4}|\n(?:photo credit|source):", excerpt, re.I):
                score -= 2
            if excerpt[0].islower() and len(excerpt) > 45:
                score -= 3
            if len(excerpt.split()) > 7 and "\n" not in excerpt and excerpt[-1] in ".!?":
                score += 1.5
            if score > best[0]:
                best = (score, excerpt, field)
    return best[1], best[2]


def _fingerprint(page):
    # Preserve numerical distinctions such as annual estimates, drop slide counters.
    text = " ".join(line for line in (page["body"] + "\n" + page["notes"]).splitlines()
                    if not line.strip().isdigit())
    words = re.findall(r"\w+", _normalize(text))
    numbers = {w for w in words if w.isdigit() and not re.fullmatch(r"(?:19|20)\d\d", w)}
    if not numbers:
        # Annual report front matter often differs only in the year. Keep
        # numerically distinct observations in the same series available.
        words = ["<year>" if re.fullmatch(r"(?:19|20)\d\d", w) else w for w in words]
    return set(zip(words, words[1:], words[2:])), numbers


def _duplicate(fingerprint, previous):
    grams, numbers = fingerprint
    for existing, nums in previous:
        if grams and nums == numbers and len(grams & existing) >= .82 * len(grams | existing):
            return True
    return False


HOUSEKEEPING = re.compile(
    r"following selected powerpoint slides|slides (?:provide|form) the (?:basis|core) for a presentation"
    r"|^\s*(?:(?:slide \d+|\d+)\s+)?(?:bibliography|references|acknowledg(?:e)?ments|thank you"
    r"|media contacts?|table of contents|presentation outline|questions and answers)\b"
    r"|presentation is (?:available|downloadable) (?:at|from)|download (?:this|these|the) (?:presentation|slides) at",
    re.I
)


class BriefIndex:
    def __init__(self, pages, stats, page_features):
        self.stats = stats
        self.pages = pages
        self._fields = []
        self._df = Counter()
        self._postings = defaultdict(set)
        deck_fields = {}
        for i, (page, (content, title)) in enumerate(zip(pages, page_features, strict=True)):
            if page["deck_id"] not in deck_fields:
                deck_fields[page["deck_id"]] = Features.of(page["deck_title"] + " " + page["topic"])
                # A national programme issued by a named national authority can
                # be scoped to that country. A foreign venue/publisher alone
                # cannot ground a geographic claim about an ordinary slide.
                metadata = deck_fields[page["deck_id"]]
                if ("national" in metadata.words and not metadata.places
                        and re.search(r"ministry|government|directorate", page["publisher"], re.I)):
                    metadata.places.update(Features.of(page["publisher"]).places)
            deck = deck_fields[page["deck_id"]]
            self._fields.append((content, title, deck))
            tokens = content.words | content.concepts | content.places
            self._df.update(tokens)
            for token in tokens | deck.places | deck.concepts | deck.words:
                self._postings[token].add(i)

    def search(self, topic: str, limit: int, *, sectors: Sequence[str] = (), min_year: int | None = None) -> list[dict]:
        if not topic.strip() or limit < 1:
            return []
        q = Features.of(topic)
        # Known concepts and places already cover their English and Chinese spellings.
        residual = GEO_RE.sub(" ", TERM_RE.sub(" ", _normalize(topic)))
        keywords = _words(residual)
        candidates = set().union(*(self._postings[t] for t in q.words | q.places | q.concepts))
        focus = q.concepts - WIDE
        multi_section = len(focus - SPECIES) >= 3
        requested_years = {w for w in q.words if re.fullmatch(r"(?:19|20)\d\d", w)}
        ranked = []
        for i in sorted(candidates):
            page = self.pages[i]
            if min_year is not None:
                issued = re.match(r"^(?:19|20)\d{2}", page.get("issued") or "")
                if not issued or int(issued[0]) < min_year:
                    continue
            if sectors and page["sector"] not in sectors:
                continue
            body, title, deck = self._fields[i]
            if HOUSEKEEPING.search(page["body"][:900]):
                continue
            page_geo = body.places or deck.places
            if q.places and not q.places & page_geo:
                continue
            if q.places and not q.places & (deck.places | title.places):
                # A citation or footnote may name a country in an otherwise unrelated
                # source. For cross-country sources look for a visible content line.
                local_lines = [line for line in page["body"].splitlines()
                               if not re.search(r"et al|https?://|copyright|doi:|^source:", line, re.I)]
                if not any(q.places & _matches(_normalize(line), GEO, GEO_RE)
                           and len(_words(_normalize(line))) >= 3 for line in local_lines):
                    continue
            if (page["series"] and len(requested_years) == 1
                    and set(re.findall(r"(?:19|20)\d\d", page["deck_title"])).isdisjoint(requested_years)
                    and re.search(r"(?:19|20)\d\d", page["deck_title"])):
                continue
            if not multi_section and q.concepts & SPECIES and not q.concepts & SPECIES & (body.concepts | deck.concepts):
                continue
            if "animal" in q.concepts and page["sector"] == "human" and "animal" not in body.concepts:
                continue
            if len(body.words | body.concepts) < 3:
                continue
            hits = q.concepts & body.concepts
            words = q.words & body.words
            # Named institutions/programmes, uncommon technical words etc. must
            # appear in this collection. An unsupported geography/topic returns a gap.
            if not multi_section and keywords and not keywords & (body.words | deck.words):
                continue
            if focus and not focus & body.concepts and not keywords & body.words:
                continue
            if "mg/kg" in q.concepts and "mg/kg" not in body.concepts:
                continue
            if not hits and not keywords & body.words:
                # A broad request can draw on relevant animal-health measures in
                # a matching source, but country/title alone never makes a slide evidence.
                if not (body.concepts - WIDE and (q.concepts & deck.concepts or q.places & deck.places)):
                    continue
            if not q.concepts and not q.places and not keywords & body.words:
                continue
            score = sum((1 + math.log((len(self.pages) + 1) / (1 + self._df[t])))
                        * (1.65 if t in title.words else 1) for t in words)
            score += sum((3 if t in focus else 1) * (1.65 if t in title.concepts else 1)
                         for t in hits)
            score += 1.5 * len(q.places & body.places) + .5 * len(q.concepts & deck.concepts)
            score += 2 * len(q.places & deck.places)
            if not hits and not words:
                score += .25 * min(4, len(body.concepts - WIDE))
            evidence_terms = sorted(hits | (keywords & body.words))
            detail = ", ".join(evidence_terms or sorted(body.concepts - WIDE)[:4])
            context = ", ".join(sorted(q.places & page_geo))
            reason = "Page evidence: " + (detail or ", ".join(sorted(words)))
            if context:
                reason += f". Geographic match ({'page' if q.places & body.places else 'source'}): {context}"
            ranked.append((score, i, reason))
        ranked.sort(key=lambda r: (-r[0], self.pages[r[1]]["deck_id"], self.pages[r[1]]["slide_number"]))
        # Greedy diversification only among close candidates. The best evidence for
        # a narrow national topic can legitimately come from a single deck.
        selected, fingerprints, sources, stages = [], [], Counter(), Counter()
        while ranked and len(selected) < limit:
            def utility(index):
                score, i, _ = ranked[index]
                page = self.pages[i]
                return score / (1 + .08 * sources[page["deck_id"]] + .04 * stages[page["stage"]])

            pos = max(range(min(len(ranked), 30)), key=utility)
            score, i, reason = ranked.pop(pos)
            page = self.pages[i]
            fp = _fingerprint(page)
            if _duplicate(fp, fingerprints):
                continue
            fingerprints.append(fp)
            evidence, field = _evidence(page, q)
            if not evidence:
                continue
            selected.append(dict(page, score=round(score, 4), reason=reason,
                                 evidence=evidence, evidence_field=field))
            sources[page["deck_id"]] += 1
            stages[page["stage"]] += 1
        return selected


def read_verified_manifest(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"id", "title", "source_page", "download_url", "sha256"}
        if not required <= set(reader.fieldnames or ()):
            raise ValueError("verified.csv requires id, title, source_page, download_url and sha256")
        rows = list(reader)
    if len(rows) > MAX_LIBRARY_FILES:
        raise ValueError("Verified corpus exceeds the supported file limit")
    seen = set()
    for row in rows:
        key = row["id"]
        if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}", key)
                or key.endswith(".") or PureWindowsPath(key).is_reserved() or key.casefold() in seen):
            raise ValueError("Invalid or duplicate deck id in verified.csv")
        if not re.fullmatch(r"[a-f0-9]{64}", row["sha256"]) or not row["title"].strip():
            raise ValueError(f"Missing verified SHA-256 or title for {key}")
        for field in ("source_page", "download_url"):
            url = urlsplit(row[field])
            if url.scheme not in {"https", "http"} or not url.hostname or url.username is not None:
                raise ValueError(f"Invalid public source attribution for {key}")
        seen.add(key.casefold())
    return rows


def build_brief_index(corpus_dir: Path, index_path: Path | None = None) -> BriefIndex:
    """Refresh the manifest-scoped SQLite cache, checking bytes even on a warm run."""
    root = Path(corpus_dir)
    manifest = root / "verified.csv"
    if not manifest.is_file():
        raise ValueError("verified.csv is missing. Fetch the public corpus first.")
    rows = read_verified_manifest(manifest)
    cache = Path(index_path) if index_path is not None else root / "brief_index.sqlite3"
    cache.parent.mkdir(parents=True, exist_ok=True)
    stats = dict(decks=0, slides=0, reused_decks=0, parsed_decks=0, failures=[], index_path=str(cache))
    pages, page_features = [], []
    with closing(sqlite3.connect(cache, timeout=90)) as db, db:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("BEGIN IMMEDIATE")
        db.execute("""CREATE TABLE IF NOT EXISTS brief_decks_v1 (
                   deck_id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, source_url TEXT NOT NULL,
                   metadata TEXT NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS brief_slides_v1 (
                   deck_id TEXT REFERENCES brief_decks_v1 ON DELETE CASCADE,
                   slide_number INTEGER, slide_id TEXT, title TEXT, body TEXT, notes TEXT,
                   PRIMARY KEY (deck_id, slide_number))""")
        db.execute("""CREATE TABLE IF NOT EXISTS brief_terms_v2 (
                   deck_id TEXT, slide_number INTEGER, features TEXT,
                   PRIMARY KEY (deck_id, slide_number), FOREIGN KEY(deck_id, slide_number)
                   REFERENCES brief_slides_v1(deck_id, slide_number) ON DELETE CASCADE)""")
        db.execute("CREATE TABLE IF NOT EXISTS brief_cache_version (version INTEGER PRIMARY KEY)")
        if db.execute("SELECT version FROM brief_cache_version").fetchone() != (2,):
            # Revision 2 includes editable chart labels in slide text.
            db.execute("DELETE FROM brief_decks_v1")
            db.execute("DELETE FROM brief_cache_version")
            db.execute("INSERT INTO brief_cache_version VALUES (2)")
        old = {r[0]: (r[1], r[2]) for r in db.execute("SELECT deck_id,sha256,source_url FROM brief_decks_v1")}
        active = set()
        for row in rows:
            key, checksum, source = row["id"], row["sha256"], row["source_page"]
            filename = key + ".pptx"
            path = root / "presentations" / filename
            try:
                if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
                    raise ValueError("Verified source missing, oversized or a symlink")
                with path.open("rb") as f:
                    if hashlib.file_digest(f, "sha256").hexdigest() != checksum:
                        raise ValueError("Source SHA-256 differs from verified.csv")
                metadata = json.dumps(row, ensure_ascii=False)
                if old.get(key) == (checksum, source):
                    db.execute("UPDATE brief_decks_v1 SET metadata=? WHERE deck_id=? AND metadata<>?",
                               (metadata, key, metadata))
                    stats["reused_decks"] += 1
                else:
                    deck = parse_presentation(path, source_url=source, source_key=filename)
                    if not deck.slides or deck.slides[0].source_hash != checksum:
                        raise ValueError("Source empty or changed while parsing")
                    db.execute("INSERT OR REPLACE INTO brief_decks_v1 VALUES (?,?,?,?)",
                               (key, checksum, source, metadata))
                    db.executemany("INSERT INTO brief_slides_v1 VALUES (?,?,?,?,?,?)",
                                   ((key, s.slide_number, s.id, s.title, s.text, s.notes) for s in deck.slides))
                    stats["parsed_decks"] += 1
            except (OSError, ValueError, KeyError, TypeError, BadZipFile, PackageNotFoundError) as exc:
                stats["failures"].append({"deck_id": key, "reason": str(exc)})
                continue
            active.add(key)
            fields = {name: row.get(name) or "" for name in
                      ("publisher", "author", "license", "sector", "topic", "issued", "language", "series")}
            fields.update(deck_id=key, deck_name=filename, deck_title=row["title"], source_url=source,
                          download_url=row["download_url"], source_hash=checksum)
            for number, sid, title, body, notes, stored in db.execute(
                    "SELECT slide_number,slide_id,title,body,notes,features FROM brief_slides_v1 "
                    "LEFT JOIN brief_terms_v2 USING (deck_id,slide_number) WHERE deck_id=? ORDER BY slide_number",
                    (key,)):
                if stored:
                    features = [Features(*(set(v) for v in fields)) for fields in json.loads(stored)]
                else:
                    features = [Features.of(body + "\n" + notes), Features.of(title)]
                    packed = [[sorted(f.words), sorted(f.concepts), sorted(f.places)] for f in features]
                    db.execute("INSERT INTO brief_terms_v2 VALUES (?,?,?)", (key, number, json.dumps(packed)))
                page_features.append(features)
                pages.append(dict(fields, slide_number=number, slide_id=sid, title=title, body=body,
                                  notes=notes, stage=_stage(title, body, features[0].concepts)))
            if len(pages) > 25_000:
                raise ValueError("Verified corpus exceeds the supported slide limit")
        db.executemany("DELETE FROM brief_decks_v1 WHERE deck_id=?", ((k,) for k in old.keys() - active))
    stats.update(decks=len(active), slides=len(pages))
    return BriefIndex(pages, stats, page_features)
