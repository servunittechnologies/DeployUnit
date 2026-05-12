/**
 * <TabBar> — mobile-first horizontal tabs.
 *
 *   Desktop (≥ md): the familiar horizontal tab strip with icons + accent
 *                   underline on the active tab.
 *   Mobile  (< md): a styled native <select> so EVERY option is reachable
 *                   with one tap. No fragile horizontal scrolling.
 *
 * Usage:
 *   const tabs = [
 *     { id: "integrations", label: "Integrations", icon: Database },
 *     { id: "plans", label: "Plans & Pricing", icon: Coins },
 *   ];
 *   <TabBar tabs={tabs} value={tab} onChange={setTab} testIdPrefix="admin-tab" />
 */
import { ChevronDown } from "lucide-react";

export default function TabBar({ tabs, value, onChange, testIdPrefix = "tab", className = "" }) {
  return (
    <div className={`mb-6 ${className}`} data-testid={`${testIdPrefix}-bar`}>
      {/* Mobile: native select */}
      <div className="md:hidden relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full appearance-none bg-[#0a0a0a] border border-white/[0.08] text-white font-mono text-sm py-3 pl-4 pr-10 focus:border-brand outline-none"
          data-testid={`${testIdPrefix}-mobile-select`}
        >
          {tabs.map((t) => (
            <option key={t.id} value={t.id}>{t.label}</option>
          ))}
        </select>
        <ChevronDown className="h-4 w-4 text-brand absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
      </div>

      {/* Desktop: horizontal tab strip */}
      <div className="hidden md:flex items-center gap-1 border-b border-white/[0.06] overflow-x-auto">
        {tabs.map((t) => {
          const Icon = t.icon;
          const active = value === t.id;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => onChange(t.id)}
              data-testid={`${testIdPrefix}-${t.id}`}
              className={`relative inline-flex items-center gap-2 px-4 py-3 text-sm whitespace-nowrap transition-colors ${
                active ? "text-brand" : "text-zinc-400 hover:text-white"
              }`}
            >
              {Icon && <Icon className="h-4 w-4" />}
              {t.label}
              {active && <span className="absolute inset-x-0 -bottom-px h-px bg-brand" />}
            </button>
          );
        })}
      </div>
    </div>
  );
}
