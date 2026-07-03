import { clsx } from "clsx";

type Variant = "green" | "yellow" | "red" | "blue" | "gray";

const variants: Record<Variant, string> = {
  green:  "bg-spotify-green/20 text-spotify-green",
  yellow: "bg-yellow-500/20 text-yellow-400",
  red:    "bg-red-500/20 text-red-400",
  blue:   "bg-blue-500/20 text-blue-400",
  gray:   "bg-white/10 text-spotify-muted",
};

interface BadgeProps {
  label: string;
  variant?: Variant;
  className?: string;
}

export function Badge({ label, variant = "gray", className }: BadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        variants[variant],
        className
      )}
    >
      {label}
    </span>
  );
}
