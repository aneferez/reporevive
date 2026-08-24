import { AlertTriangle, CircleCheck, CircleX, Info } from "lucide-react";
import type { Severity } from "../types";

const labels: Record<Severity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
};

const icons = {
  critical: CircleX,
  high: AlertTriangle,
  medium: Info,
  low: CircleCheck,
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  const Icon = icons[severity];
  return (
    <span className={`severity-badge severity-${severity}`}>
      <Icon size={13} strokeWidth={2.2} />
      {labels[severity]}
    </span>
  );
}
