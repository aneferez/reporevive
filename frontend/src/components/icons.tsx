import type { SVGProps } from "react";

export function BrandMark({ size = 38, className = "" }: { size?: number; className?: string }) {
  return (
    <svg aria-hidden="true" className={className} width={size} height={size} viewBox="0 0 48 48" fill="none">
      <path d="M24 5.5 40.5 15v18L24 42.5 7.5 33V15L24 5.5Z" stroke="currentColor" strokeWidth="2.3" />
      <path d="m7.8 15.2 16.2 9.3 16.2-9.3M24 24.5v17.2" stroke="currentColor" strokeWidth="2.3" strokeLinejoin="round" />
      <path d="m16.3 10.2 16.4 9.4-8.7 5-16.4-9.4 8.7-5Z" fill="currentColor" opacity=".36" />
      <path d="m32.7 10.2-16.4 9.4 8.7 5 16.4-9.4-8.7-5Z" fill="currentColor" opacity=".82" />
    </svg>
  );
}

export function OrbitSpark({ className = "" }: { className?: string }) {
  return (
    <svg aria-hidden="true" className={className} width="28" height="28" viewBox="0 0 28 28" fill="none">
      <circle cx="14" cy="14" r="4" fill="currentColor" />
      <path d="M14 2v5M14 21v5M2 14h5M21 14h5M5.5 5.5 9 9M19 19l3.5 3.5M22.5 5.5 19 9M9 19l-3.5 3.5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}
