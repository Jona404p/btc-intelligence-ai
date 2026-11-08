"use client";

import { useState, ReactNode } from "react";

export interface TabDef {
  id: string;
  label: string;
  icon?: ReactNode;
  /** Optional small colored dot to surface state at a glance (e.g. bullish/bearish). */
  dotColor?: string;
  content: ReactNode;
}

export default function Tabs({
  tabs,
  defaultTab,
  onTabChange,
}: {
  tabs: TabDef[];
  defaultTab?: string;
  /** Notifica a quien use Tabs qué pestaña quedó activa, para poder pausar
   *  fetching/polling en segundo plano de las pestañas que no se están viendo. */
  onTabChange?: (id: string) => void;
}) {
  const [active, setActive] = useState(defaultTab || tabs[0]?.id);
  const activeTab = tabs.find((t) => t.id === active) ?? tabs[0];

  function handleSelect(id: string) {
    setActive(id);
    onTabChange?.(id);
  }

  return (
    <div>
      <div className="rounded-xl border border-border bg-panel-muted p-1">
        <nav className="flex gap-1 overflow-x-auto no-scrollbar" role="tablist" aria-label="Secciones de inteligencia de mercado">
          {tabs.map((tab) => {
            const isActive = tab.id === activeTab?.id;
            return (
              <button
                key={tab.id}
                role="tab"
                aria-selected={isActive}
                onClick={() => handleSelect(tab.id)}
                  className={`relative flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm whitespace-nowrap transition-colors ${
                    isActive ? "bg-panel text-foreground shadow-sm" : "text-muted hover:text-foreground"
                  }`}
              >
                {tab.dotColor && (
                  <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: tab.dotColor }} />
                )}
                {tab.icon}
                {tab.label}
                <span
                  className={`absolute left-0 right-0 -bottom-px h-0.5 rounded-full transition-colors ${
                    isActive ? "bg-neutral" : "bg-transparent"
                  }`}
                />
              </button>
            );
          })}
        </nav>
      </div>
      <div className="pt-4">{activeTab?.content}</div>
    </div>
  );
}
