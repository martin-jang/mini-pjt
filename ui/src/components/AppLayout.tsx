import { Link, NavLink, Outlet, useLocation } from 'react-router';
import { useSites } from '../hooks/useSites';
import { siteHome } from '../lib/format';
import { Icon } from './Icon';
import { Logo } from './Logo';
import { StatusBadge } from './StatusBadge';

const PAGE_LABEL: Record<string, string> = {
  analysis: '분석 리뷰',
  design: '디자인 확인',
  result: '결과',
};

function Breadcrumb() {
  const { pathname } = useLocation();
  const parts = pathname.split('/').filter(Boolean);
  let crumbs: string[];
  if (parts[0] === 'sites' && parts[1]) {
    crumbs = ['사이트', parts[1], PAGE_LABEL[parts[2] ?? ''] ?? '진행 상황'];
  } else if (parts[0] === 'query') {
    crumbs = ['질의'];
  } else {
    crumbs = ['새 요청'];
  }
  return (
    <nav aria-label="현재 위치" className="flex items-center gap-2 text-sm">
      {crumbs.map((c, i) => (
        <span key={`${c}-${i}`} className="flex items-center gap-2">
          {i > 0 && <span className="text-mute">/</span>}
          <span className={i === crumbs.length - 1 ? 'font-medium text-ink' : 'text-body'}>
            {c}
          </span>
        </span>
      ))}
    </nav>
  );
}

const navItemClass = (active: boolean) =>
  `relative flex h-9 items-center justify-between gap-2 rounded-md px-3 text-sm transition-colors ${
    active
      ? 'bg-canvas-soft-2 font-medium text-ink'
      : 'text-body hover:bg-canvas-soft-2 hover:text-ink'
  }`;

function Sidebar() {
  const sites = useSites();
  const { pathname } = useLocation();
  return (
    <aside className="fixed inset-y-0 left-0 flex w-60 flex-col border-r border-hairline bg-canvas-soft">
      <div className="flex h-14 items-center px-5">
        <Link to="/new" aria-label="Legacy2Next 처음 화면">
          <Logo />
        </Link>
      </div>
      <div className="px-4">
        <Link
          to="/new"
          data-testid="nav-new-request"
          className="flex h-9 items-center justify-center gap-1.5 rounded-md bg-ink text-sm font-medium text-white hover:opacity-90"
        >
          <Icon name="add" />새 요청
        </Link>
      </div>
      <p className="mt-6 px-5 text-xs font-medium text-mute">사이트</p>
      <ul className="mt-2 flex-1 space-y-0.5 overflow-y-auto px-3" data-testid="site-list">
        {sites.map((site) => {
          const active = pathname.startsWith(`/sites/${site.alias}`);
          return (
            <li key={site.alias}>
              <Link
                to={siteHome(site.alias, site.status)}
                data-testid={`site-${site.alias}`}
                className={navItemClass(active)}
              >
                <span className="truncate font-mono text-[13px]">{site.alias}</span>
                <StatusBadge status={site.status} plain />
              </Link>
            </li>
          );
        })}
      </ul>
      <div className="border-t border-hairline p-3">
        <NavLink
          to="/query"
          data-testid="nav-query"
          className={({ isActive }) => navItemClass(isActive)}
        >
          <span className="flex items-center gap-2">
            <Icon name="chat_bubble" className="text-body" />
            질의
          </span>
        </NavLink>
      </div>
    </aside>
  );
}

export function AppLayout() {
  return (
    <div className="min-h-screen">
      <Sidebar />
      <div className="pl-60">
        <header className="sticky top-0 z-10 flex h-14 items-center justify-between border-b border-hairline bg-canvas px-8">
          <Breadcrumb />
          <span className="flex size-8 items-center justify-center rounded-full border border-hairline text-body">
            <Icon name="person" />
          </span>
        </header>
        <main className="mx-auto max-w-[1120px] px-8 pt-12 pb-12">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
