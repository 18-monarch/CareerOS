import { notFound } from "next/navigation";
import Workspace from "@/components/workspace";
const sections = [
  "research",
  "application-desk",
  "opportunities",
  "applications",
  "learning",
  "campus",
  "projects",
  "dsa",
  "market",
  "sources",
  "notifications",
  "profile",
];
export default async function Page({
  params,
}: {
  params: Promise<{ section: string }>;
}) {
  const { section } = await params;
  if (!sections.includes(section)) notFound();
  return <Workspace section={section} />;
}
