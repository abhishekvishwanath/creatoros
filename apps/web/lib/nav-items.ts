import {
  Home,
  Compass,
  Lightbulb,
  PenSquare,
  CalendarDays,
  BarChart3,
  Dna,
  Building2,
  Send,
  FlaskConical,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Home", icon: Home },
  { href: "/research", label: "Research", icon: Compass },
  { href: "/opportunities", label: "Opportunities", icon: Lightbulb },
  { href: "/create", label: "Create", icon: PenSquare },
  { href: "/calendar", label: "Calendar", icon: CalendarDays },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/experiments", label: "Experiments", icon: FlaskConical },
  { href: "/brands", label: "Brands", icon: Building2 },
  { href: "/outreach", label: "Outreach", icon: Send },
  { href: "/creator-dna", label: "Creator DNA", icon: Dna },
];
