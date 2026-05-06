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
        background: "rgba(8,12,20,0.95)",
        borderTop: "1px solid rgba(255,255,255,0.07)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        boxShadow: "0 -4px 24px rgba(0,0,0,0.4)",
      }}
    >
      {items.map(({ path, label, icon: Icon }) => (
        <NavLink
          key={path}
          to={path}
          className={({ isActive }) =>
            cn(
              "flex-1 flex flex-col items-center justify-center gap-1 py-2 px-1 relative",
              "text-[0.58rem] font-medium tracking-[0.04em] cursor-pointer",
              "transition-colors duration-150 focus-visible:outline-none",
              isActive ? "text-midground" : "text-midground/35 hover:text-midground/65",
            )
          }
        >
          {({ isActive }) => (
            <>
              <span
                className="relative flex items-center justify-center"
                style={isActive ? {
                  filter: "drop-shadow(0 0 6px rgba(204,0,0,0.5))",
                } : undefined}
              >
                <Icon className={cn("h-5 w-5 shrink-0 transition-colors", isActive && "text-[#ff5060]")} />
                {isActive && (
                  <span
                    aria-hidden
                    className="absolute -bottom-2 left-1/2 -translate-x-1/2 h-0.5 w-4 rounded-full"
                    style={{ background: "linear-gradient(90deg, #CC0000, #ee2d3f)", boxShadow: "0 0 6px rgba(204,0,0,0.7)" }}
                  />
                )}
              </span>
              <span className="leading-none mt-1">{label}</span>
            </>
          )}
        </NavLink>
      ))}

      <button
        type="button"
        onClick={onMore}
        className={cn(
          "flex-1 flex flex-col items-center justify-center gap-1 py-2 px-1",
          "text-[0.58rem] font-medium tracking-[0.04em] cursor-pointer",
          "text-midground/35 hover:text-midground/65 transition-colors duration-150",
          "focus-visible:outline-none",
        )}
      >
        <MoreHorizontal className="h-5 w-5 shrink-0" />
        <span className="leading-none mt-1">More</span>
      </button>
    </nav>
  );
}
