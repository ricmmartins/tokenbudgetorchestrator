import { NextResponse } from "next/server";

const ENGINE_URL = process.env.TBO_ENGINE_URL || "http://localhost:8000";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const workspace = searchParams.get("workspace") || "default";

  try {
    const res = await fetch(`${ENGINE_URL}/v1/workspaces/${workspace}/agents`, {
      headers: { "Content-Type": "application/json" },
    });

    if (!res.ok) {
      return NextResponse.json(
        { error: "Engine unavailable" },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    // Engine not running — return mock data for development
    return NextResponse.json({
      workspace,
      agents: [
        { id: "support-bot", tokens: 45200, budget: 200000, cost: 2.15, status: "ok" },
        { id: "code-reviewer", tokens: 32100, budget: 50000, cost: 4.82, status: "warning" },
        { id: "report-gen", tokens: 12800, budget: 500000, cost: 1.92, status: "ok" },
      ],
    });
  }
}
