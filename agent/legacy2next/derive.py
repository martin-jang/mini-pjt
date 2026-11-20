"""파생 데이터 만들기 (T07b): 원본 dom.min.html만 읽어 layout·components·tokens를 만든다.

브라우저·LLM 없이 같은 입력이면 같은 결과가 나온다 (재분석·재현용).
dom.min.html의 요소에는 고정 추출 스크립트가 붙인 위치(data-l2n-box)와
스타일(data-l2n-style)이 있다.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Literal

from .crawl import (
    Box,
    Components,
    Density,
    Form,
    FormField,
    Layout,
    MenuItem,
    PageLink,
    Paging,
    Region,
    RegionRole,
    Table,
    TokenCount,
    Tokens,
    Viewport,
)

VOID = {"img", "br", "hr", "input", "wbr", "area", "col", "meta", "link"}
INTERACTIVE = {"a", "button", "input", "select", "textarea"}
FIELD_SKIP_TYPES = {"hidden", "submit", "button", "image", "reset"}
TOP_N = 12

# 영역 판별: 시맨틱 태그 → role 속성 → id·class 단어 순으로 본다
REGION_TAGS: dict[str, RegionRole] = {
    "header": "header",
    "nav": "nav",
    "main": "main",
    "aside": "aside",
    "footer": "footer",
}
REGION_ROLES: dict[str, RegionRole] = {
    "banner": "header",
    "navigation": "nav",
    "main": "main",
    "complementary": "aside",
    "contentinfo": "footer",
}
REGION_WORDS: list[tuple[RegionRole, re.Pattern[str]]] = [
    ("header", re.compile(r"(^|[-_ ])(header|top|gnb)([-_ ]|$)")),
    ("nav", re.compile(r"(^|[-_ ])(nav|menu|lnb|snb|sidebar|side-menu)([-_ ]|$)")),
    ("footer", re.compile(r"(^|[-_ ])(footer|bottom|copyright)([-_ ]|$)")),
    ("aside", re.compile(r"(^|[-_ ])(aside|side)([-_ ]|$)")),
    ("main", re.compile(r"(^|[-_ ])(content|contents|main|container)([-_ ]|$)")),
]
PAGING_WORDS = re.compile(r"pag(e|ing|ination)", re.I)
TAB_WORDS = re.compile(r"(^|[-_ ])tabs?([-_ ]|$)", re.I)
RGB = re.compile(r"rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)")


@dataclass
class Node:
    tag: str
    attrs: dict[str, str]
    children: list[Node] = field(default_factory=list)
    text: str = ""  # 이 요소에 바로 들어 있는 글자
    parent: Node | None = None

    def iter(self) -> Iterator[Node]:
        yield self
        for c in self.children:
            yield from c.iter()

    def all_text(self) -> str:
        parts = [self.text, *(c.all_text() for c in self.children)]
        return " ".join(p for p in parts if p).strip()

    @property
    def box(self) -> Box | None:
        raw = self.attrs.get("data-l2n-box")
        if not raw:
            return None
        try:
            x, y, w, h = (int(v) for v in raw.split(","))
        except ValueError:
            return None
        return Box(x=x, y=y, width=w, height=h)

    @property
    def style(self) -> dict[str, str]:
        raw = self.attrs.get("data-l2n-style", "")
        return dict(part.split("=", 1) for part in raw.split(";") if "=" in part)

    @property
    def words(self) -> str:
        return f"{self.attrs.get('id', '')} {self.attrs.get('class', '')}".lower()

    def selector(self) -> str:
        s = self.tag
        if self.attrs.get("id"):
            s += f"#{self.attrs['id']}"
        if self.attrs.get("class"):
            s += "." + ".".join(self.attrs["class"].split()[:2])
        return s


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("document", {})
        self._stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, {k: v or "" for k, v in attrs}, parent=self._stack[-1])
        self._stack[-1].children.append(node)
        if tag not in VOID:
            self._stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i].tag == tag:
                del self._stack[i:]
                return

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            node = self._stack[-1]
            node.text = f"{node.text} {text}".strip()


def parse_dom(html: str) -> Node:
    builder = _TreeBuilder()
    builder.feed(html)
    builder.close()
    return builder.root


def _html_attr(root: Node, name: str) -> str:
    html = next((n for n in root.iter() if n.tag == "html"), None)
    return html.attrs.get(name, "") if html else ""


def _pair(raw: str, default: tuple[int, int]) -> tuple[int, int]:
    try:
        a, b = (int(v) for v in raw.split(","))
        return a, b
    except ValueError:
        return default


# ── 레이아웃 ─────────────────────────────


def _region_role(node: Node) -> RegionRole | None:
    if node.tag in REGION_TAGS:
        return REGION_TAGS[node.tag]
    role = node.attrs.get("role", "")
    if role in REGION_ROLES:
        return REGION_ROLES[role]
    if node.tag in ("div", "section", "ul", "td", "table"):
        for region, pattern in REGION_WORDS:
            if pattern.search(node.words):
                return region
    return None


def derive_layout(root: Node) -> Layout:
    vw, vh = _pair(_html_attr(root, "data-l2n-viewport"), (1280, 720))
    _, page_h = _pair(_html_attr(root, "data-l2n-page"), (vw, vh))
    best: dict[RegionRole, tuple[int, Node, Box]] = {}
    for node in root.iter():
        role = _region_role(node)
        box = node.box
        if role is None or box is None or box.width <= 0 or box.height <= 0:
            continue
        area = box.width * box.height
        if role not in best or area > best[role][0]:
            best[role] = (area, node, box)
    regions = [
        Region(role=role, box=box, selector=node.selector())
        for role, (_, node, box) in sorted(best.items(), key=lambda kv: (kv[1][2].y, kv[1][2].x))
    ]

    menu = "none"
    if "nav" in best:
        nav = best["nav"][2]
        if nav.height > nav.width and nav.x < vw * 0.35:
            menu = "left"
        elif nav.height > nav.width and nav.x > vw * 0.65:
            menu = "right"
        else:
            menu = "top"

    nodes = [n for n in root.iter() if n.tag not in ("document", "html", "head", "title")]
    interactive = sum(1 for n in nodes if n.tag in INTERACTIVE)
    text_blocks = sum(1 for n in nodes if n.text)
    screens = max(1.0, page_h / vh) if vh else 1.0
    density = Density(
        elements=len(nodes),
        interactive=interactive,
        text_blocks=text_blocks,
        interactive_per_screen=round(interactive / screens, 1),
    )
    return Layout(
        viewport=Viewport(width=vw, height=vh),
        page_height=page_h,
        regions=regions,
        menu=menu,  # type: ignore[arg-type]
        density=density,
        main_columns=_main_columns(best.get("main", (0, None, None))[1]),
    )


def _main_columns(main: Node | None) -> int:
    """본문 영역 바로 아래 블록들이 가로로 몇 줄(열)로 놓였는지."""
    if main is None or main.box is None:
        return 1
    width = main.box.width
    xs = sorted(
        c.box.x
        for c in main.children
        if c.box and c.box.width > 0 and c.box.height > 0 and c.box.width < width * 0.9
    )
    columns: list[int] = []
    for x in xs:
        if not columns or x - columns[-1] > 8:
            columns.append(x)
    return max(1, len(columns))


# ── 컴포넌트 ─────────────────────────────


def _label_for(field: Node, labels: dict[str, str]) -> str:
    if field.attrs.get("id") and field.attrs["id"] in labels:
        return labels[field.attrs["id"]]
    parent = field.parent
    while parent is not None:
        if parent.tag == "label":
            return parent.all_text()
        parent = parent.parent
    for key in ("aria-label", "placeholder", "title", "name"):
        if field.attrs.get(key):
            return field.attrs[key]
    return ""


def _field(node: Node, labels: dict[str, str]) -> FormField | None:
    if node.tag == "input":
        kind = node.attrs.get("type", "text").lower() or "text"
        if kind in FIELD_SKIP_TYPES:
            return None
    elif node.tag in ("select", "textarea"):
        kind = node.tag
    else:
        return None
    max_length = node.attrs.get("maxlength", "")
    return FormField(
        label=_label_for(node, labels),
        name=node.attrs.get("name", ""),
        type=kind,
        required="required" in node.attrs,
        pattern=node.attrs.get("pattern") or None,
        max_length=int(max_length) if max_length.isdigit() else None,
        options=[o.all_text() for o in node.iter() if o.tag == "option"][:30],
    )


def _button_label(node: Node) -> str | None:
    if node.tag == "button":
        return node.all_text() or node.attrs.get("aria-label", "")
    if node.tag == "input" and node.attrs.get("type", "").lower() in ("submit", "button", "reset"):
        return node.attrs.get("value", "") or node.attrs.get("aria-label", "") or node.attrs["type"]
    if node.tag == "a" and (node.attrs.get("role") == "button" or "btn" in node.words):
        return node.all_text()
    return None


def _table(node: Node) -> Table:
    rows = [r for r in node.iter() if r.tag == "tr"]
    header_row = next((r for r in rows if any(c.tag == "th" for c in r.children)), None)
    if header_row is None and rows:
        header_row = rows[0]
    headers = (
        [c.all_text() for c in header_row.children if c.tag in ("th", "td")] if header_row else []
    )
    body_rows = [r for r in rows if r is not header_row]
    return Table(headers=headers, rows=len(body_rows))


def _is_paging(node: Node) -> list[str] | None:
    links = [n for n in node.children if n.tag in ("a", "strong", "span", "li", "button")]
    labels = [n.all_text() for n in links if n.all_text()]
    numeric = [label for label in labels if label.isdigit()]
    if PAGING_WORDS.search(node.words) and labels:
        return labels
    if len(numeric) >= 2 and len(numeric) >= len(labels) / 2:
        return labels
    return None


def derive_components(root: Node) -> Components:
    labels = {
        n.attrs["for"]: n.all_text() for n in root.iter() if n.tag == "label" and n.attrs.get("for")
    }
    forms: list[Form] = []
    in_form: set[int] = set()
    for form in (n for n in root.iter() if n.tag == "form"):
        fields = []
        submits = []
        for n in form.iter():
            in_form.add(id(n))
            f = _field(n, labels)
            if f:
                fields.append(f)
            label = _button_label(n)
            if label:
                submits.append(label)
        forms.append(
            Form(method=form.attrs.get("method", "get").lower(), fields=fields, submits=submits)
        )
    loose = [f for n in root.iter() if id(n) not in in_form and (f := _field(n, labels))]
    if loose:
        forms.append(Form(method="none", fields=loose))

    tabs = []
    for n in root.iter():
        if n.attrs.get("role") == "tablist" or (
            n.tag in ("ul", "ol", "div") and TAB_WORDS.search(n.words)
        ):
            items = [c.all_text() for c in n.children if c.all_text()]
            if len(items) >= 2:
                tabs.append(items)

    paging = []
    seen_paging: set[int] = set()
    for n in root.iter():
        if n.tag in ("div", "nav", "ul", "p", "td", "span") and id(n.parent) not in seen_paging:
            found = _is_paging(n)
            if found:
                paging.append(Paging(labels=found))
                seen_paging.update(id(x) for x in n.iter())

    return Components(
        tables=[_table(n) for n in root.iter() if n.tag == "table"],
        forms=forms,
        buttons=[label for n in root.iter() if (label := _button_label(n))],
        tabs=tabs,
        paging=paging,
        links=sum(1 for n in root.iter() if n.tag == "a"),
    )


# ── 토큰 ─────────────────────────────


def _hex(color: str) -> str | None:
    m = RGB.match(color.strip())
    if not m:
        return None
    r, g, b, a = m.groups()
    if a is not None and float(a) == 0:
        return None  # 투명
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"


def _is_gray(hex_color: str) -> bool:
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return max(r, g, b) - min(r, g, b) < 16


def _top(counter: Counter[str]) -> list[TokenCount]:
    return [TokenCount(value=v, count=c) for v, c in counter.most_common(TOP_N)]


def derive_tokens(root: Node) -> Tokens:
    text_colors: Counter[str] = Counter()
    backgrounds: Counter[str] = Counter()
    families: Counter[str] = Counter()
    sizes: Counter[str] = Counter()
    weights: Counter[str] = Counter()
    spacing: Counter[str] = Counter()
    radius: Counter[str] = Counter()
    for n in root.iter():
        s = n.style
        if not s:
            continue
        if n.text:  # 글자가 있는 요소의 글꼴·글자색만 센다
            if color := _hex(s.get("c", "")):
                text_colors[color] += 1
            if s.get("ff"):
                families[s["ff"]] += 1
            if s.get("fs"):
                sizes[f"{s['fs']}px"] += 1
            if s.get("fw"):
                weights[s["fw"]] += 1
        if bg := _hex(s.get("bg", "")):
            backgrounds[bg] += 1
        for key in ("p", "m"):
            for v in s.get(key, "").split():
                if v not in ("0", ""):
                    spacing[f"{v}px"] += 1
        if s.get("br", "0") != "0":
            radius[f"{s['br']}px"] += 1
    accents = Counter({c: n for c, n in (text_colors + backgrounds).items() if not _is_gray(c)})
    return Tokens(
        text_colors=_top(text_colors),
        background_colors=_top(backgrounds),
        accent_colors=_top(accents),
        font_families=_top(families),
        font_sizes=_top(sizes),
        font_weights=_top(weights),
        spacing=_top(spacing),
        radius=_top(radius),
    )


def derive_all(html: str) -> tuple[Layout, Components, Tokens]:
    root = parse_dom(html)
    return derive_layout(root), derive_components(root), derive_tokens(root)


# ── 링크·메뉴 (T07c Map) ─────────────────────────────

# 따라가지 않는 파일 내려받기 주소
DOWNLOAD_EXT = re.compile(
    r"\.(pdf|zip|hwp|hwpx|xls|xlsx|doc|docx|ppt|pptx|csv|txt|jpg|png|gif)$", re.I
)
MAX_MENU_ITEMS = 200


def link_area(node: Node) -> str:
    """링크가 놓인 영역 (가장 가까운 영역 조상). 없으면 other."""
    parent = node.parent
    while parent is not None:
        role = _region_role(parent)
        if role:
            return role
        parent = parent.parent
    return "other"


def _href_kind(href: str) -> Literal["url", "script", "anchor", "none"]:
    """주소 종류. 주소 없는 링크(javascript:, #, 빈 값)는 스크립트 메뉴로 보고 클릭 대상이 된다."""
    h = href.strip().lower()
    if h.startswith("javascript:") or h in ("", "#"):
        return "script"
    if h.startswith("#"):
        return "anchor"
    if h.startswith(("mailto:", "tel:")):
        return "none"
    return "url"


def extract_links(root: Node) -> list[PageLink]:
    """화면의 링크 목록 (문서 순서, 같은 화면 안 앵커 제외)."""
    links: list[PageLink] = []
    for n in root.iter():
        if n.tag != "a":
            continue
        label = n.all_text() or n.attrs.get("title", "") or n.attrs.get("aria-label", "")
        href = n.attrs.get("href", "")
        kind: str = _href_kind(href)
        if kind == "anchor":
            continue
        if kind == "url" and DOWNLOAD_EXT.search(href.split("?", 1)[0]):
            kind = "download"
        links.append(PageLink(label=label[:100], href=href, kind=kind, area=link_area(n)))  # type: ignore[arg-type]
    return links


def _menu_items(node: Node) -> list[MenuItem]:
    """ul/ol 중첩을 메뉴 트리로. li 안의 첫 링크(또는 글자)가 항목 이름이다."""
    items: list[MenuItem] = []
    for li in (c for c in node.children if c.tag == "li"):
        link = next((d for d in li.iter() if d.tag == "a"), None)
        sub = next((d for d in li.iter() if d is not li and d.tag in ("ul", "ol")), None)
        if link is not None and sub is not None and _contains(sub, link):
            link = None  # 첫 링크가 하위 메뉴 안에 있으면 이 항목은 이름만 있다
        label = (link.all_text() if link else li.text) or ""
        children = _menu_items(sub) if sub else []
        if label or children:
            items.append(
                MenuItem(
                    label=label[:100],
                    href=link.attrs.get("href") if link else None,
                    children=children,
                )
            )
    return items


def _contains(tree: Node, target: Node) -> bool:
    return any(n is target for n in tree.iter())


def extract_menu(root: Node) -> list[MenuItem]:
    """메뉴 영역(nav, 없으면 header)의 메뉴 트리."""
    areas = [n for n in root.iter() if _region_role(n) == "nav"]
    if not areas:
        areas = [n for n in root.iter() if _region_role(n) == "header"]
    # 바깥 영역 안에 들어 있는 영역은 바깥 것으로 합친다
    areas = [a for a in areas if not any(o is not a and _contains(o, a) for o in areas)]
    menu: list[MenuItem] = []
    seen: set[tuple[str, str | None]] = set()
    for area in areas:
        lists = [n for n in area.iter() if n.tag in ("ul", "ol")]
        top = [u for u in lists if not any(o is not u and _contains(o, u) for o in lists)]
        if top:
            items = [item for u in top for item in _menu_items(u)]
        else:
            items = [
                MenuItem(label=a.all_text()[:100], href=a.attrs.get("href"))
                for a in area.iter()
                if a.tag == "a" and a.all_text()
            ]
        for item in items:
            key = (item.label, item.href)
            if key not in seen and len(seen) < MAX_MENU_ITEMS:
                seen.add(key)
                menu.append(item)
    return menu
