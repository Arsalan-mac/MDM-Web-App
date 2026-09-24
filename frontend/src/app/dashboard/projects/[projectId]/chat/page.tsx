"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { ApiError, sendChatMessage, type ChatTurn } from "@/lib/api";

export default function ChatPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { getToken } = useAuth();
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const message = input.trim();
    if (!message || sending) return;

    setInput("");
    setError(null);
    const history = turns;
    setTurns([...history, { role: "user", content: message }]);
    setSending(true);

    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const reply = await sendChatMessage(token, projectId, message, history);
      setTurns((prev) => [...prev, { role: "assistant", content: reply }]);
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setError(
          "The chat agent isn't configured yet - the backend needs an ANTHROPIC_API_KEY.",
        );
      } else {
        setError(err instanceof Error ? err.message : "Something went wrong.");
      }
      // Roll back the optimistically-added user turn so a retry doesn't duplicate it.
      setTurns(history);
    } finally {
      setSending(false);
    }
  }

  return (
    <main style={{ padding: "3rem", maxWidth: 700, margin: "0 auto" }}>
      <p>
        <Link href={`/dashboard/projects/${projectId}`}>← Back to project</Link>
      </p>
      <h1>💬 Talk to your data</h1>
      <p style={{ color: "#666" }}>
        Ask about this project&apos;s pipeline status or Address Cleansing findings. Read-only -
        it can&apos;t change anything for you; use the Address Cleansing page&apos;s Accept
        button for that.
      </p>

      <div
        style={{
          border: "1px solid #ccc",
          borderRadius: 8,
          minHeight: 300,
          maxHeight: 500,
          overflowY: "auto",
          padding: "1rem",
          margin: "1rem 0",
          display: "flex",
          flexDirection: "column",
          gap: "0.75rem",
        }}
      >
        {turns.length === 0 && (
          <p style={{ color: "#999" }}>
            Try: &quot;What&apos;s the pipeline status?&quot; or &quot;How many address
            problems are there?&quot;
          </p>
        )}
        {turns.map((t, i) => (
          <div key={i} style={{ alignSelf: t.role === "user" ? "flex-end" : "flex-start", maxWidth: "85%" }}>
            <div
              style={{
                background: t.role === "user" ? "#0070f3" : "#f0f0f0",
                color: t.role === "user" ? "white" : "black",
                borderRadius: 8,
                padding: "0.5rem 0.75rem",
                whiteSpace: "pre-wrap",
              }}
            >
              {t.content}
            </div>
          </div>
        ))}
        {sending && <p style={{ color: "#999" }}>Thinking…</p>}
      </div>

      {error && <p style={{ color: "crimson" }}>{error}</p>}

      <form onSubmit={handleSend} style={{ display: "flex", gap: "0.5rem" }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question…"
          style={{ flex: 1, padding: "0.5rem" }}
          disabled={sending}
        />
        <button type="submit" disabled={sending || !input.trim()}>
          Send
        </button>
      </form>
    </main>
  );
}
