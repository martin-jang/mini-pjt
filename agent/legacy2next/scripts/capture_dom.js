() => {
  // Legacy2Next 고정 추출 스크립트 (읽기 전용, G1 예외). LLM이 내용을 만들거나 바꾸지 않는다.
  // 화면 DOM을 줄여 HTML 문자열로 돌려준다. 요소마다 위치(data-l2n-box)와 적용된 스타일(data-l2n-style)을
  // 붙여 두므로, 브라우저 없이 이 HTML만으로 레이아웃·컴포넌트·토큰을 다시 만들 수 있다.
  // 입력란 값(value)은 저장하지 않는다 (계정·개인정보).
  const MAX_NODES = 6000;
  const MAX_TEXT = 200;
  const SKIP = new Set([
    'SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'LINK', 'META', 'HEAD',
    'IFRAME', 'OBJECT', 'EMBED', 'CANVAS', 'VIDEO', 'AUDIO',
  ]);
  const VOID = new Set(['img', 'br', 'hr', 'input', 'wbr', 'area', 'col']);
  const KEEP = [
    'id', 'class', 'name', 'type', 'href', 'role', 'aria-label', 'aria-selected', 'aria-current',
    'placeholder', 'required', 'pattern', 'maxlength', 'minlength', 'min', 'max', 'for',
    'colspan', 'rowspan', 'method', 'action', 'alt', 'title', 'disabled', 'readonly', 'multiple',
  ];
  let count = 0;
  const esc = (s) =>
    String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const px = (v) => String(Math.round(parseFloat(v) || 0));
  const box = (el) => {
    const r = el.getBoundingClientRect();
    return [r.left + scrollX, r.top + scrollY, r.width, r.height].map((n) => Math.round(n)).join(',');
  };
  const style = (cs) =>
    [
      'c=' + cs.color,
      'bg=' + cs.backgroundColor,
      'ff=' + cs.fontFamily.split(',')[0].replace(/["']/g, '').trim(),
      'fs=' + px(cs.fontSize),
      'fw=' + cs.fontWeight,
      'p=' + [cs.paddingTop, cs.paddingRight, cs.paddingBottom, cs.paddingLeft].map(px).join(' '),
      'm=' + [cs.marginTop, cs.marginRight, cs.marginBottom, cs.marginLeft].map(px).join(' '),
      'br=' + px(cs.borderTopLeftRadius),
      'd=' + cs.display,
    ].join(';');

  function walk(node) {
    if (count >= MAX_NODES) return '';
    if (node.nodeType === 3) {
      const t = node.textContent.replace(/\s+/g, ' ').trim();
      return t ? esc(t.slice(0, MAX_TEXT)) + ' ' : '';
    }
    if (node.nodeType !== 1) return '';
    const el = node;
    if (SKIP.has(el.tagName.toUpperCase())) return '';
    if (el instanceof SVGElement) return el.tagName.toLowerCase() === 'svg' ? `<svg data-l2n-box="${box(el)}"></svg>` : '';
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return '';
    count++;
    const tag = el.tagName.toLowerCase();
    let attrs = '';
    for (const a of KEEP) {
      if (!el.hasAttribute(a)) continue;
      let v = el.getAttribute(a) || '';
      if (a === 'class') v = v.trim().split(/\s+/).slice(0, 6).join(' ');
      if (a === 'href' && /^javascript:/i.test(v)) v = 'javascript:';
      attrs += ` ${a}="${esc(v.slice(0, 300))}"`;
    }
    // 버튼형 입력의 value는 버튼 글자라 남긴다 (그 외 입력값은 남기지 않는다)
    if (tag === 'input' && /^(submit|button|reset)$/i.test(el.type)) attrs += ` value="${esc(el.value.slice(0, 100))}"`;
    attrs += ` data-l2n-box="${box(el)}" data-l2n-style="${esc(style(cs))}"`;
    if (tag === 'textarea') return `<textarea${attrs}></textarea>`;
    if (VOID.has(tag)) return `<${tag}${attrs}>`;
    let inner = '';
    for (const child of el.childNodes) inner += walk(child);
    return `<${tag}${attrs}>${inner}</${tag}>`;
  }

  const body = walk(document.body);
  const doc = document.documentElement;
  return (
    `<!doctype html><html data-l2n-url="${esc(location.href)}"` +
    ` data-l2n-viewport="${innerWidth},${innerHeight}"` +
    ` data-l2n-page="${doc.scrollWidth},${doc.scrollHeight}"` +
    ` data-l2n-truncated="${count >= MAX_NODES}">` +
    `<head><title>${esc(document.title)}</title></head>${body}</html>`
  );
}
