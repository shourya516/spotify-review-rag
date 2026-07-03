import { clsx } from "clsx";
import { HTMLAttributes } from "react";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  padding?: boolean;
}

export function Card({ padding = true, className, children, ...props }: CardProps) {
  return (
    <div
      className={clsx(
        "rounded-xl bg-spotify-card border border-white/5",
        padding && "p-5",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}
