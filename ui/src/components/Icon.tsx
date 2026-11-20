interface IconProps {
  name: string;
  className?: string;
}

/** Material Symbols Outlined 아이콘 */
export function Icon({ name, className = '' }: IconProps) {
  return (
    <span aria-hidden="true" className={`material-symbols-outlined text-[18px] ${className}`}>
      {name}
    </span>
  );
}
