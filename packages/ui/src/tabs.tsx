import type { ButtonHTMLAttributes } from "react";

export function Tab({
  active,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { active: boolean }) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      className="he-tab"
      data-active={active}
      {...props}
    />
  );
}
