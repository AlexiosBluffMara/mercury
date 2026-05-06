import { BarChart3, Cpu, MessageSquare, MoreHorizontal, Sparkles, Terminal } from "lucide-react";
import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";

interface BottomNavProps {
  onMore: () => void;
  showChat: boolean;
}

export function BottomNav({ onMore, showChat }: BottomNavProps) {
  const items = showChat
    ? [
        { path: "/sessions", label: "Sessions", icon: MessageSquare },
        { path: "/chat", label: "Chat", icon: Terminal },
        { path: "/brains", label: "Brains", icon: Cpu },
        { path: "/cortex", label: "Cortex", icon: Sparkles },
      ]
    : [
        { path: "/sessions", label: "Sessions", icon: MessageSquare },
        { path: "/brains", label: "Brains", icon: Cpu },
        { path: "/cortex", label: "Cortex", icon: Sparkles },
        { path: "/analytics", label: "Stats", icon: BarChart3 },
      ];

  return (
    <nav
      className="lg:hidden fixed bottom-0 left-0 right-0 z-40 flex items-stretch h-16"
      style={{
        background: "var(--component-header-background)",
        borderTop: "1px solid color-mix(in srgb, var(--midground-base) 20%, transparent)",
      }}
    >
      {items.map(({ path, label, icon: Icon }) => (
        <NavLink
          key={path}
          to={path}
          className={({ isActive }) =>
            cn(
              "flex-1 flex flex-col items-center justify-center gap-0.5 py-2 px-1",
              "font-mondwest text-[0.55rem] tracking-[0.06em] uppercase cursor-pointer",
              "transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-midground/40",
              isActive ? "text-midground" : "text-midground/40 hover:text-midground/70",
            )
          }
        >
          {({ isActive }) => (
            <>
              <Icon className={cn("h-5 w-5 shrink-0", isActive && "drop-shadow-sm")} />
              <span className="leading-none">{label}</span>
            </>
          )}
        </NavLink>
      ))}

      <button
        type="button"
        onClick={onMore}
        className={cn(
          "flex-1 flex flex-col items-center justify-center gap-0.5 py-2 px-1",
          "font-mondwest text-[0.55rem] tracking-[0.06em] uppercase cursor-pointer",
          "text-midground/40 hover:text-midground/70 transition-colors",
          "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-midground/40",
        )}
      >
        <MoreHorizontal className="h-5 w-5 shrink-0" />
        <span className="leading-none">More</span>
      </button>
    </nav>
  );
}
