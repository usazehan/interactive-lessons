"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";

import BlockView from "@/app/components/BlockView";
import {
  getProject,
  listBlocks,
  listSections,
  type ContentBlock,
  type Project,
  type Section,
} from "@/lib/api";

export default function ProjectPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const projectId = Number(use(params).id);

  const [project, setProject] = useState<Project | null>(null);
  const [sections, setSections] = useState<Section[]>([]);
  const [current, setCurrent] = useState(0);
  const [blocks, setBlocks] = useState<ContentBlock[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getProject(projectId), listSections(projectId)])
      .then(([p, s]) => {
        setProject(p);
        setSections(s);
      })
      .catch((e) => setError(e.message ?? "failed to load project"));
  }, [projectId]);

  const activeSection = sections[current];

  useEffect(() => {
    if (!activeSection) return;
    setBlocks(null);
    listBlocks(projectId, activeSection.id)
      .then(setBlocks)
      .catch((e) => setError(e.message ?? "failed to load section"));
  }, [projectId, activeSection]);

  if (error) {
    return (
      <p className="rounded border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-300">
        {error}
      </p>
    );
  }
  if (!project) return <p className="text-sm text-black/60">Loading…</p>;

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/"
          className="text-sm text-black/50 underline-offset-4 hover:underline dark:text-white/50"
        >
          ← All lessons
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">{project.name}</h1>
        {project.description && (
          <p className="text-black/60 dark:text-white/60">
            {project.description}
          </p>
        )}
      </div>

      {sections.length === 0 ? (
        <p className="text-sm text-black/60">This lesson has no steps yet.</p>
      ) : (
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-[14rem_1fr]">
          {/* step sidebar */}
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

          {/* content */}
          <article className="min-w-0 space-y-5">
            <h2 className="text-lg font-semibold">
              {activeSection?.title ?? `Step ${current + 1}`}
            </h2>

            {blocks === null ? (
              <p className="text-sm text-black/60">Loading…</p>
            ) : blocks.length === 0 ? (
              <p className="text-sm text-black/60">This step is empty.</p>
            ) : (
              blocks.map((b) => <BlockView key={b.id} block={b} />)
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
