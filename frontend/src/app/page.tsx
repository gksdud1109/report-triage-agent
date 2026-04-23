"use client";

import { useEffect, useState } from "react";

const QUEUES = [
  "fraud-review",
  "spam-review",
  "abuse-review",
  "general-review",
] as const;

type Queue = (typeof QUEUES)[number];

type QueueItem = {
  report_id: string;
  queue_status: string;
  category: string;
  priority: string;
  requires_review: boolean;
  enqueued_at: string;
};

type QueueListResponse = {
  queue_name: string;
  items: QueueItem[];
  next_cursor: string | null;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const PRIORITY_COLOR: Record<string, string> = {
  critical: "#d1242f",
  high: "#bc4c00",
  medium: "#bf8700",
  low: "#1a7f37",
};

export default function Page() {
  const [queue, setQueue] = useState<Queue>("fraud-review");
  const [items, setItems] = useState<QueueItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load(target: Queue) {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `${API_BASE}/queues/${target}/reports?limit=20`,
        { cache: "no-store" },
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: QueueListResponse = await res.json();
      setItems(data.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setItems([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load(queue);
  }, [queue]);

  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: "32px 24px" }}>
      <header style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, margin: 0 }}>Report Triage — 큐 브라우저</h1>
        <p style={{ color: "#57606a", fontSize: 13, margin: "6px 0 0" }}>
          API: <code>{API_BASE}</code>
        </p>
      </header>

      <nav style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        {QUEUES.map((q) => {
          const active = q === queue;
          return (
            <button
              key={q}
              onClick={() => setQueue(q)}
              style={{
                padding: "8px 14px",
                border: "1px solid",
                borderColor: active ? "#1f6feb" : "#d0d7de",
                background: active ? "#1f6feb" : "#ffffff",
                color: active ? "#ffffff" : "#1f2328",
                borderRadius: 6,
                cursor: "pointer",
                fontSize: 13,
                fontWeight: active ? 600 : 400,
              }}
            >
              {q}
            </button>
          );
        })}
        <button
          onClick={() => load(queue)}
          style={{
            marginLeft: "auto",
            padding: "8px 14px",
            border: "1px solid #d0d7de",
            background: "#f6f8fa",
            borderRadius: 6,
            cursor: "pointer",
            fontSize: 13,
          }}
        >
          새로고침
        </button>
      </nav>

      <section
        style={{
          background: "#ffffff",
          border: "1px solid #d0d7de",
          borderRadius: 8,
          overflow: "hidden",
        }}
      >
        {loading && (
          <div style={{ padding: 16, color: "#57606a", fontSize: 13 }}>
            불러오는 중…
          </div>
        )}
        {error && (
          <div style={{ padding: 16, color: "#d1242f", fontSize: 13 }}>
            오류: {error}
          </div>
        )}
        {!loading && !error && items.length === 0 && (
          <div style={{ padding: 16, color: "#57606a", fontSize: 13 }}>
            이 큐에는 아직 신고가 없습니다.
          </div>
        )}
        {!loading && !error && items.length > 0 && (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead style={{ background: "#f6f8fa" }}>
              <tr>
                <Th>report_id</Th>
                <Th>category</Th>
                <Th>priority</Th>
                <Th>review</Th>
                <Th>queue_status</Th>
                <Th>enqueued_at</Th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <tr key={it.report_id} style={{ borderTop: "1px solid #eaeef2" }}>
                  <Td mono>{it.report_id}</Td>
                  <Td>{it.category}</Td>
                  <Td>
                    <span
                      style={{
                        color: PRIORITY_COLOR[it.priority] ?? "#57606a",
                        fontWeight: 600,
                      }}
                    >
                      {it.priority}
                    </span>
                  </Td>
                  <Td>{it.requires_review ? "YES" : "no"}</Td>
                  <Td>{it.queue_status}</Td>
                  <Td mono>{formatTs(it.enqueued_at)}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th
      style={{
        textAlign: "left",
        padding: "10px 12px",
        fontWeight: 600,
        color: "#57606a",
        fontSize: 12,
      }}
    >
      {children}
    </th>
  );
}

function Td({
  children,
  mono = false,
}: {
  children: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <td
      style={{
        padding: "10px 12px",
        fontFamily: mono
          ? "ui-monospace, SFMono-Regular, Menlo, monospace"
          : undefined,
      }}
    >
      {children}
    </td>
  );
}

function formatTs(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toISOString().replace("T", " ").slice(0, 19);
  } catch {
    return iso;
  }
}
