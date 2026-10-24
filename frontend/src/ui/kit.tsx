// MuGuard's pixel component set. Frames, buttons, fields and chips share the notched 4px frame in index.css.

import type { AnchorHTMLAttributes, ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, Ref, TextareaHTMLAttributes } from "react";
import { Sprite } from "../sprites";
import { ICONS, type IconName } from "./icons";

export function Icon({ name, size = 2, className, label }: { name: IconName; size?: number; className?: string; label?: string }) {
  return <Sprite rows={ICONS[name]} scale={size} className={`shrink-0 ${className ?? ""}`} label={label} />;
}

export function Spinner({ label = "Working" }: { label?: string }) {
  return (
    <span className="px-spinner" role="status" aria-label={label}>
      <i />
      <i />
      <i />
    </span>
  );
}

type Look = { variant?: "primary" | "secondary" | "dark" | "ghost"; size?: "sm" | "md" | "lg" | "xl"; icon?: IconName; iconRight?: IconName };

const looks = ({ variant = "secondary", size = "md" }: Look, extra?: string) =>
  `px-btn px-btn-${variant} ${size === "md" ? "" : `px-btn-${size}`} ${extra ?? ""}`;

const iconScale = (size: Look["size"]) => (size === "xl" || size === "lg" ? 3 : 2);

export function Button({ variant, size, icon, iconRight, loading, className, children, disabled, ref, ...rest }: Look & { loading?: boolean; ref?: Ref<HTMLButtonElement> } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button ref={ref} type="button" {...rest} disabled={disabled || loading} aria-busy={loading || undefined} className={looks({ variant, size }, className)}>
      {loading ? <Spinner /> : icon && <Icon name={icon} size={iconScale(size)} />}
      <span>{children}</span>
      {iconRight && <Icon name={iconRight} size={iconScale(size)} />}
    </button>
  );
}

export function LinkButton({ variant, size, icon, iconRight, className, children, ...rest }: Look & AnchorHTMLAttributes<HTMLAnchorElement>) {
  return (
    <a {...rest} className={looks({ variant, size }, className)}>
      {icon && <Icon name={icon} size={iconScale(size)} />}
      <span>{children}</span>
      {iconRight && <Icon name={iconRight} size={iconScale(size)} />}
    </a>
  );
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <span className="px-field block"><input {...props} className={`w-full bg-transparent px-3 py-3 outline-none ${props.className ?? ""}`} /></span>;
}

export function TextArea({ label, id, hint, ...rest }: { label: string; id: string; hint?: ReactNode } & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <div>
      <label htmlFor={id} className="px-label">
        {label}
      </label>
      <div className="px-field mt-2">
        <textarea id={id} {...rest} />
      </div>
      {hint && <p className="mt-2 text-xs text-quiet">{hint}</p>}
    </div>
  );
}

export function Chip({ children, tone, className }: { children: ReactNode; tone?: "red" | "dark"; className?: string }) {
  return <span className={`px-chip ${tone ? `px-chip-${tone}` : ""} ${className ?? ""}`}>{children}</span>;
}

export function Tabs<T extends string>({ value, options, onChange, label }: { value: T; options: [T, string][]; onChange: (v: T) => void; label: string }) {
  return (
    <div role="tablist" aria-label={label} className="px-tabs">
      {options.map(([v, text]) => (
        <button key={v} type="button" role="tab" aria-selected={value === v} onClick={() => onChange(v)} className="px-tab">
          {text}
        </button>
      ))}
    </div>
  );
}
