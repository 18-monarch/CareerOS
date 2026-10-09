"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Compass,
  LayoutDashboard,
  BriefcaseBusiness,
  PanelsTopLeft,
  BookOpen,
  GraduationCap,
  FolderGit2,
  Braces,
  ChartNoAxesCombined,
  Radio,
  Bell,
  Settings2,
  LogOut,
  Sun,
  Moon,
  Menu,
  X,
} from "lucide-react";
import { api, pretty } from "@/lib/api";
import AuthScreen from "./auth-screen";
import { Loading, ErrorBox } from "./ui";
const Dashboard = dynamic(() => import("./dashboard"));
const Opportunities = dynamic(() => import("./opportunities"));
const Applications = dynamic(() => import("./applications"));
const Profile = dynamic(() => import("./profile"));
const Learning = dynamic(() => import("./learning"));
const Projects = dynamic(() => import("./projects"));
const Campus = dynamic(() => import("./campus"));
const Sources = dynamic(() => import("./sources"));
const Market = dynamic(() => import("./market"));
const Notifications = dynamic(() => import("./notifications"));
const DSA = dynamic(() => import("./dsa"));
const Research = dynamic(() => import("./research"));
const ApplicationDesk = dynamic(() => import("./application-desk"));
const nav = [
  ["dashboard", "Overview", LayoutDashboard],
  ["research", "Internship brief", Compass],
  ["opportunities", "Opportunities", BriefcaseBusiness],
  ["application-desk", "Application desk", PanelsTopLeft],
  ["applications", "Applications", PanelsTopLeft],
  ["learning", "Learn → Apply", BookOpen],
  ["campus", "Nirma campus", GraduationCap],
  ["projects", "Project mastery", FolderGit2],
  ["dsa", "DSA readiness", Braces],
  ["market", "Market notes", ChartNoAxesCombined],
  ["sources", "Sources", Radio],
  ["notifications", "Notifications", Bell],
  ["profile", "My profile", Settings2],
] as const;
export default function Workspace({ section }: { section: string }) {
  const client = useQueryClient();
  const router = useRouter();
  const [open, setOpen] = useState(false),
    [light, setLight] = useState(false),
    [logoutError, setLogoutError] = useState<Error | null>(null);
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api<{ id: string; name: string; email: string }>("/auth/me"),
    retry: false,
  });
  useEffect(() => {
    const saved = localStorage.getItem("careeros-theme");
    setLight(saved === "light");
    document.documentElement.dataset.theme = saved || "dark";
    const expired = () => {
      client.setQueryData(["me"], null);
      client.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" });
    };
    window.addEventListener("auth-expired", expired);
    return () => window.removeEventListener("auth-expired", expired);
  }, [client]);
  function toggleTheme() {
    const next = !light;
    setLight(next);
    document.documentElement.dataset.theme = next ? "light" : "dark";
    localStorage.setItem("careeros-theme", next ? "light" : "dark");
  }
  if (me.isPending)
    return (
      <main className="boot">
        <div className="brand">
          <Compass />
          CareerOS
        </div>
        <Loading />
      </main>
    );
  if (!me.data)
    return <AuthScreen onLogin={() => client.invalidateQueries()} />;
  const views: Record<string, React.ReactNode> = {
    dashboard: <Dashboard name={me.data.name} />,
    research: <Research />,
    "application-desk": <ApplicationDesk />,
    opportunities: <Opportunities />,
    applications: <Applications />,
    learning: <Learning />,
    profile: <Profile />,
    projects: <Projects />,
    campus: <Campus />,
    sources: <Sources />,
    market: <Market />,
    notifications: <Notifications />,
    dsa: <DSA />,
  };
  return (
    <div className="workspace">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      {open && (
        <button
          className="sidebar-scrim"
          onClick={() => setOpen(false)}
          aria-label="Close navigation"
        />
      )}
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="brand">
          <Compass size={25} />
          <b>CareerOS</b>
          <span className="version">1.0</span>
          <button
            onClick={() => setOpen(false)}
            className="icon-button mobile"
            aria-label="Close navigation"
          >
            <X size={20} />
          </button>
        </div>
        <div className="workspace-label">PERSONAL WORKSPACE</div>
        <nav>
          {nav.map(([id, title, Icon], i) => (
            <Link
              key={id}
              href={id === "dashboard" ? "/" : `/${id}`}
              onClick={() => setOpen(false)}
              className={`${section === id ? "active" : ""} ${i === 5 || i === 8 ? "nav-separator" : ""}`}
              aria-current={section === id ? "page" : undefined}
            >
              <Icon size={18} />
              {title}
              {id === "opportunities" && <span className="nav-dot" />}
            </Link>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="profile-chip">
            <span className="avatar">
              {me.data.name
                .split(" ")
                .map((n) => n[0])
                .slice(0, 2)
                .join("")}
            </span>
            <div>
              <b>{me.data.name}</b>
              <small>Your career workspace</small>
            </div>
          </div>
          <button
            className="text-button"
            onClick={async () => {
              try {
                await api("/auth/logout", { method: "POST" });
                client.clear();
                router.push("/");
                router.refresh();
              } catch (e) {
                setLogoutError(e as Error);
              }
            }}
          >
            <LogOut size={15} />
            Sign out
          </button>
          <ErrorBox error={logoutError} />
        </div>
      </aside>
      <div className="main-wrap">
        <div className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile"
              onClick={() => setOpen(true)}
              aria-label="Open navigation"
            >
              <Menu size={20} />
            </button>
            <span>Workspace</span>
            <span>/</span>
            <strong>
              {section === "dashboard" ? "Overview" : pretty(section)}
            </strong>
          </div>
          <div className="topbar-actions">
            <span className="private-label">
              <span />
              Private workspace
            </span>
            <button
              className="icon-button"
              onClick={toggleTheme}
              aria-label={light ? "Use dark theme" : "Use light theme"}
            >
              {light ? <Moon size={18} /> : <Sun size={18} />}
            </button>
            <Link
              href="/notifications"
              className="icon-button"
              aria-label="View notifications"
            >
              <Bell size={18} />
            </Link>
          </div>
        </div>
        <main id="main" className="main-content">
          {views[section]}
        </main>
        <footer className="workspace-footer">
          CareerOS <span>Clear decisions. Steady progress.</span>
        </footer>
      </div>
    </div>
  );
}
