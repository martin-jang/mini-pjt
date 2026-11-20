import type { SiteMapLinkStatus, SiteMapMenuItem, SiteMapView } from '../api/types';
import { Card } from './Card';
import { Badge, Dot, type Tone } from './StatusBadge';

const LINK_STATUS: Record<SiteMapLinkStatus, { label: string; tone: Tone }> = {
  blocked: { label: '차단', tone: 'error' },
  skipped: { label: '건너뜀', tone: 'waiting' },
  limit: { label: '상한', tone: 'pending' },
  failed: { label: '실패', tone: 'error' },
};

function pathOf(url: string): string {
  try {
    const u = new URL(url);
    return `${u.pathname}${u.search}`;
  } catch {
    return url;
  }
}

function MenuTree({ items, depth = 0 }: { items: SiteMapMenuItem[]; depth?: number }) {
  return (
    <ul className={depth > 0 ? 'mt-1 ml-4 space-y-1' : 'space-y-1'}>
      {items.map((item, i) => (
        <li key={`${item.label}-${i}`}>
          <span
            className="flex items-center gap-2 text-sm"
            data-testid="sitemap-menu-item"
            data-collected={item.screenId ? 'true' : 'false'}
          >
            <Dot tone={item.screenId ? 'success' : 'pending'} />
            <span className={item.screenId ? 'text-ink' : 'text-mute'}>{item.label}</span>
          </span>
          {item.children.length > 0 && <MenuTree items={item.children} depth={depth + 1} />}
        </li>
      ))}
    </ul>
  );
}

/** Explorer Map 결과: 메뉴 트리, 수집 화면 목록, 따라가지 않은 링크와 이유 */
export function SiteMapCard({ sitemap }: { sitemap: SiteMapView }) {
  const count = (k: string) => sitemap.edgeCounts[k] ?? 0;
  const summary = [
    `화면 ${sitemap.screens.length}개`,
    `이동 ${count('followed') + count('duplicate')}`,
    `차단 ${count('blocked')}`,
    `건너뜀 ${count('skipped')}`,
    `상한 ${count('limit')}`,
  ].join(' · ');

  return (
    <Card
      title="사이트맵"
      className="mt-6"
      testId="sitemap"
      actions={
        <span className="text-xs text-body" data-testid="sitemap-summary">
          {summary}
          {sitemap.truncated && ' · 화면 수 상한에 닿음'}
        </span>
      }
      bodyClassName="p-0"
    >
      <div className="grid grid-cols-[260px_1fr] divide-x divide-hairline">
        <div className="p-5">
          <p className="mb-3 text-xs text-body">메뉴</p>
          {sitemap.menu.length === 0 ? (
            <p className="text-sm text-mute">메뉴 영역을 찾지 못했습니다.</p>
          ) : (
            <MenuTree items={sitemap.menu} />
          )}
        </div>
        <table className="w-full text-sm" data-testid="sitemap-screens">
          <thead className="bg-canvas-soft-2 text-left text-xs text-body">
            <tr>
              <th className="px-5 py-2.5 font-normal">수집 화면</th>
              <th className="px-3 py-2.5 font-normal">경로</th>
              <th className="px-3 py-2.5 text-right font-normal">깊이</th>
              <th className="px-3 py-2.5 font-normal">구성</th>
              <th className="px-5 py-2.5 text-right font-normal">들어오는 이동</th>
            </tr>
          </thead>
          <tbody>
            {sitemap.screens.map((s) => (
              <tr key={s.screenId} className="border-t border-hairline">
                <td className="px-5 py-2.5">{s.title || '(제목 없음)'}</td>
                <td className="max-w-[280px] truncate px-3 py-2.5 font-mono text-xs text-body">
                  {pathOf(s.url)}
                </td>
                <td className="px-3 py-2.5 text-right">{s.depth}</td>
                <td className="px-3 py-2.5 text-xs text-body">
                  표 {s.tables} · 폼 {s.forms} · 버튼 {s.buttons}
                </td>
                <td className="px-5 py-2.5 text-right">{s.inbound}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {sitemap.notFollowed.length > 0 && (
        <details className="border-t border-hairline px-5 py-3" data-testid="sitemap-not-followed">
          <summary className="cursor-pointer text-sm text-body">
            따라가지 않은 링크 {sitemap.notFollowed.length}개
          </summary>
          <ul className="mt-2 space-y-1.5">
            {sitemap.notFollowed.map((link, i) => (
              <li key={i} className="flex items-center gap-3 text-sm">
                <Badge tone={LINK_STATUS[link.status].tone} plain>
                  {LINK_STATUS[link.status].label}
                </Badge>
                <span className="text-ink">{link.label || '(이름 없음)'}</span>
                <span className="text-xs text-body">{link.reason}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </Card>
  );
}
