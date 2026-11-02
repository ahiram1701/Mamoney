import { ChevronLeft, ChevronRight } from "lucide-react";

import { monthName, shiftMonth, thisMonth } from "../lib/month";

export function MonthNav({ month, onChange }: { month: string; onChange: (m: string) => void }) {
  return (
    <div className="mb-4 flex items-center gap-2">
      <button
        className="btn btn-sm"
        onClick={() => onChange(shiftMonth(month, -1))}
        aria-label="Mes anterior"
      >
        <ChevronLeft size={16} />
      </button>
      <h2 className="min-w-40 text-center font-semibold first-letter:uppercase">
        {monthName(month)}
      </h2>
      <button
        className="btn btn-sm"
        onClick={() => onChange(shiftMonth(month, 1))}
        disabled={month >= thisMonth()}
        aria-label="Mes siguiente"
      >
        <ChevronRight size={16} />
      </button>
    </div>
  );
}
