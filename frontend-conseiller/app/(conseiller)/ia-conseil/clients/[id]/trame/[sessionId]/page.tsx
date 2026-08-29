"use client";

import { useParams } from "next/navigation";

import { SessionTrameWorkspace } from "@/components/ia-conseil/SessionTrameWorkspace";

export default function TrameLivePage() {
  const params = useParams<{ id: string; sessionId: string }>();
  return <SessionTrameWorkspace clientId={params.id} sessionId={params.sessionId} />;
}
