"use client";

import { useEffect, useState } from "react";

import {
  addResponse,
  listResponses,
  type SessionResponse,
} from "@/lib/api";

// A checkpoint inside a reading session: shows the reader's saved answers and a
// form to add one (a text note, a link, or both).
export default function CheckpointResponse({
  projectId,
  sessionId,
  checkpointId,
  title,
}: {
  projectId: number;
  sessionId: number;
  checkpointId: number;
  title: string;
}) {
  const [responses, setResponses] = useState<SessionResponse[]>([]);
  const [text, setText] = useState("");
  const [link, setLink] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    listResponses(projectId, sessionId, checkpointId)
      .then(setResponses)
      .catch(() => setResponses([]));
  }, [projectId, sessionId, checkpointId]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const body: { text?: string; link?: string } = {};
      if (text.trim()) body.text = text.trim();
      if (link.trim()) body.link = link.trim();
      const saved = await addResponse(projectId, sessionId, checkpointId, body);
      setResponses((r) => [...r, saved]);
      setText("");
      setLink("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not save");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-4">
      <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-400">
        Checkpoint
      </div>
      <div className="font-medium">{title}</div>

      {responses.length > 0 && (
        <ul className="mt-3 space-y-1.5 text-sm">
          {responses.map((r) => (
            <li
              key={r.id}
              className="rounded bg-white/60 px-2 py-1.5 dark:bg-white/5"
            >
              {r.text && <span>{r.text}</span>}
              {r.link && (
                <a
                  href={r.link}
                  target="_blank"
                  rel="noreferrer"
                  className="ml-1 text-blue-600 underline underline-offset-2 dark:text-blue-400"
                >
                  {r.label ?? r.link}
                </a>
              )}
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={submit} className="mt-3 space-y-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Your answer / notes"
          className="w-full rounded border border-black/15 bg-white px-2 py-1.5 text-sm dark:border-white/20 dark:bg-transparent"
        />
        <div className="flex gap-2">
          <input
            value={link}
            onChange={(e) => setLink(e.target.value)}
            placeholder="https://… (optional)"
            className="min-w-0 flex-1 rounded border border-black/15 bg-white px-2 py-1.5 text-sm dark:border-white/20 dark:bg-transparent"
          />
          <button
            type="submit"
            disabled={busy || (!text.trim() && !link.trim())}
            className="shrink-0 rounded bg-amber-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            Save
          </button>
        </div>
        {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}
      </form>
    </div>
  );
}
