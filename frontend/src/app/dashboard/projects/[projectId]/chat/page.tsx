"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { ArrowLeft, MessageCircle, Send } from "lucide-react";
import clsx from "clsx";
import { ApiError, sendChatMessage, type ChatTurn } from "@/lib/api";
import { Alert, Button, Card, Input } from "@/components/ui";

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
    <div className="space-y-6">
      <Link
        href={`/dashboard/projects/${projectId}`}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-500 hover:text-ink-800"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to project
      </Link>

      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
          <MessageCircle className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold text-ink-900">Talk to your data</h1>
          <p className="text-sm text-ink-500">
            Ask about this project&apos;s pipeline status or Address Cleansing findings.
            Read-only — it can&apos;t change anything for you; use the Address Cleansing
            page&apos;s Accept button for that.
          </p>
        </div>
      </div>

      <Card className="flex min-h-[360px] max-h-[560px] flex-col overflow-y-auto p-4">
        <div className="flex flex-1 flex-col gap-3">
          {turns.length === 0 && (
            <p className="text-sm text-ink-400">
              Try: &quot;What&apos;s the pipeline status?&quot; or &quot;How many address
              problems are there?&quot;
            </p>
          )}
          {turns.map((t, i) => (
            <div
              key={i}
              className={clsx("max-w-[85%]", t.role === "user" ? "self-end" : "self-start")}
            >
              <div
                className={clsx(
                  "whitespace-pre-wrap rounded-xl px-3.5 py-2 text-sm",
                  t.role === "user" ? "bg-brand-600 text-white" : "bg-ink-100 text-ink-800",
                )}
              >
                {t.content}
              </div>
            </div>
          ))}
          {sending && <p className="text-sm text-ink-400">Thinking…</p>}
        </div>
      </Card>

      {error && <Alert tone="danger">{error}</Alert>}

      <form onSubmit={handleSend} className="flex gap-2">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question…"
          disabled={sending}
        />
        <Button type="submit" disabled={sending || !input.trim()}>
          <Send className="h-4 w-4" />
          Send
        </Button>
      </form>
    </div>
  );
}
