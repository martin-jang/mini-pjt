import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { Icon } from './Icon';

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost';

const VARIANT_CLASS: Record<Variant, string> = {
  primary: 'border-ink bg-ink text-white hover:opacity-90',
  secondary: 'border-hairline bg-canvas text-ink hover:bg-canvas-soft',
  danger: 'border-hairline bg-canvas text-error hover:bg-error-soft',
  ghost: 'border-transparent bg-transparent text-body hover:bg-canvas-soft-2',
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  icon?: string;
  iconAfter?: string;
  children: ReactNode;
}

/** 버튼 높이 36px, 6px 모서리. 주요 버튼(ink)은 화면당 하나 */
export function Button({
  variant = 'secondary',
  icon,
  iconAfter,
  children,
  className = '',
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={`inline-flex h-9 items-center justify-center gap-1.5 rounded-md border px-3.5 text-sm font-medium whitespace-nowrap transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-running disabled:cursor-not-allowed disabled:opacity-50 ${VARIANT_CLASS[variant]} ${className}`}
      {...rest}
    >
      {icon && <Icon name={icon} />}
      {children}
      {iconAfter && <Icon name={iconAfter} />}
    </button>
  );
}
