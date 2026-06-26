"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";

import BlockView from "@/app/components/BlockView";
import CheckpointResponse from "@/app/components/CheckpointResponse";
import { useAuth } from "@/lib/auth";
import {
  refreshSession,
  startSession,
  type ReadingSession,
} from "@/lib/api";

export default function SessionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const projectId = Number(use(params).id);
  const { user, loading: authLoading } = useAuth();

  const [session, setSession] = useState<ReadingSession | null>(null);
  const [current, setCurrent] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    if (authLoading || !user) return;
    startSession(projectId)
      .then(setSession)
      .catch((e) => setError(e.message ?? "failed to start session"));
  }, [projectId, user, authLoading]);

  async function getLatest() {
    if (!session) return;
    setRefreshing(true);
    try {
      setSession(await refreshSession(projectId, session.id));
      setCurrent(0);
    } finally {
      setRefreshing(false);
    }
  }

  if (authLoading) return <p className="text-sm text-black/60">Loading…</p>;

  if (!user) {
    return (
      <p className="text-sm">
        <Link href="/login" className="underline underline-offset-4">
          Log in
        </Link>{" "}
        to start this lesson and track your progress.
      </p>
    );
  }

  if (error) {
    return (
      <p className="rounded border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-300">
        {error}
      </p>
    );
  }
  if (!session) return <p className="text-sm text-black/60">Starting…</p>;

  const sections = session.snapshot.sections;
  const activeSection = sections[current];

  return (
    <div className="space-y-6">
      <div>
        <Link
          href={`/projects/${projectId}`}
          className="text-sm text-black/50 underline-offset-4 hover:underline dark:text-white/50"
        >
          ← Lesson overview
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">Your session</h1>
        <p className="text-sm text-black/50 dark:text-white/50">
          Pinned to version {session.project_version}.
        </p>
      </div>

      {session.is_stale && (
        <div className="flex items-center justify-between gap-3 rounded-lg border border-blue-500/40 bg-blue-500/10 px-3 py-2 text-sm">
          <span>
            This lesson was updated (v{session.project_version} → v
            {session.latest_version}).
          </span>
          <button
            onClick={getLatest}
            disabled={refreshing}
            className="shrink-0 rounded bg-blue-600 px-3 py-1.5 font-medium text-white disabled:opacity-50"
          >
            {refreshing ? "Updating…" : "Get latest"}
          </button>
        </div>
      )}

      {sections.length === 0 ? (
        <p className="text-sm text-black/60">This lesson has no steps yet.</p>
      ) : (
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-[14rem_1fr]">
          <nav className="space-y-1">
            {sections.map((s, i) => (
              <button
                key={s.id}
                onClick={() => setCurrent(i)}
                className={`flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm ${
                  i === current
                    ? "bg-black/[0.06] font-medium dark:bg-white/10"
                    : "hover:bg-black/[0.03] dark:hover:bg-white/5"
                }`}
              >
                <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-black/10 text-xs dark:bg-white/15">
                  {i + 1}
                </span>
                <span className="truncate">{s.title ?? `Step ${i + 1}`}</span>
              </button>
            ))}
          </nav>

          <article className="min-w-0 space-y-5">
            <h2 className="text-lg font-semibold">
              {activeSection?.title ?? `Step ${current + 1}`}
            </h2>

            {activeSection?.blocks.length === 0 ? (
              <p className="text-sm text-black/60">This step is empty.</p>
            ) : (
              activeSection?.blocks.map((b) =>
                b.type === "checkpoint" && b.checkpoint ? (
                  <CheckpointResponse
                    key={b.id}
                    projectId={projectId}
                    sessionId={session.id}
                    checkpointId={b.checkpoint.id}
                    title={b.checkpoint.title}
                  />
                ) : (
                  <BlockView key={b.id} block={b} />
                ),
              )
            )}

            <div className="flex justify-between pt-4">
              <button
                disabled={current === 0}
                onClick={() => setCurrent((c) => c - 1)}
                className="rounded border border-black/15 px-3 py-1.5 text-sm disabled:opacity-40 dark:border-white/20"
              >
                ← Previous
              </button>
              <button
                disabled={current >= sections.length - 1}
                onClick={() => setCurrent((c) => c + 1)}
                className="rounded border border-black/15 px-3 py-1.5 text-sm disabled:opacity-40 dark:border-white/20"
              >
                Next →
              </button>
            </div>
          </article>
        </div>
      )}
    </div>
  );
}
