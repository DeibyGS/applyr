import { NavLink } from "react-router";
import { Building2, Briefcase, CalendarCheck, BarChart3, Settings } from "lucide-react";

const NAV_ITEMS = [
  { to: "/office", label: "Office", icon: Building2 },
  { to: "/offers", label: "Offers", icon: Briefcase },
  { to: "/interviews", label: "Interviews", icon: CalendarCheck },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  return (
    <nav className="flex w-56 shrink-0 flex-col gap-1 border-r border-border bg-card p-4">
      <p className="mb-4 font-display text-lg font-medium text-foreground">applyr</p>
      {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            `flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring ${
              isActive
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
            }`
          }
        >
          <Icon className="size-4" />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
