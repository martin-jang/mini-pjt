import type { ReactNode } from 'react';

interface CardProps {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  testId?: string;
}

/** 섹션: 제목은 카드 밖, 본문은 흰 카드(1px 헤어라인, 8px 모서리, 그림자 없음) */
export function Card({
  title,
  description,
  actions,
  children,
  className = '',
  bodyClassName = 'p-6',
  testId,
}: CardProps) {
  return (
    <section data-testid={testId} className={className}>
      {(title || actions) && (
        <header className="mb-3 flex items-end justify-between gap-4">
          <div>
            {title && <h2 className="text-base font-semibold text-ink">{title}</h2>}
            {description && <p className="mt-0.5 text-xs text-mute">{description}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={`rounded-lg border border-hairline bg-canvas ${bodyClassName}`}>
        {children}
      </div>
    </section>
  );
}
