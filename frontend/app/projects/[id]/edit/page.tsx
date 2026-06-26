"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";

import BlockForm from "@/app/components/BlockForm";
import BlockView from "@/app/components/BlockView";
import { useAuth } from "@/lib/auth";
import {
  ApiError,
  createBlock,
  createSection,
  deleteBlock,
  deleteSection,
  getProject,
  listBlocks,
  listSections,
  type ContentBlock,
  type NewBlock,
  type Project,
  type Section,
} from "@/lib/api";

export default function EditProjectPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const projectId = Number(use(params).id);
  const { user, loading: authLoading } = useAuth();

  const [project, setProject] = useState<Project | null>(null);
  const [sections, setSections] = useState<Section[]>([]);
  const [currentId, setCurrentId] = useState<number | null>(null);
  const [blocks, setBlocks] = useState<ContentBlock[]>([]);
  const [version, setVersion] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  const [newSection, setNewSection] = useState("");

  const load = useCallback(async () => {
    const [p, s] = await Promise.all([
      getProject(projectId),
      listSections(projectId),
    ]);
    setProject(p);
    setVersion(p.version);
    setSections(s);
    setCurrentId((cur) => cur ?? s[0]?.id ?? null);
  }, [projectId]);

  useEffect(() => {
    if (authLoading || !user) return;
    load().catch((e) => setError(e.message ?? "failed to load"));
  }, [authLoading, user, load]);

  useEffect(() => {
    if (currentId == null) {
      setBlocks([]);
      return;
    }
    listBlocks(projectId, currentId)
      .then(setBlocks)
      .catch(() => setBlocks([]));
  }, [projectId, currentId]);

  // Re-sync after a concurrent edit elsewhere bumped the version.
  async function onConflict() {
    setConflict(true);
    await load();
    if (currentId != null) setBlocks(await listBlocks(projectId, currentId));
  }

  async function guard(fn: () => Promise<void>) {
    setError(null);
    try {
      await fn();
      setConflict(false);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) await onConflict();
      else setError(e instanceof Error ? e.message : "something went wrong");
    }
  }

  const addSection = () =>
    guard(async () => {
      if (!newSection.trim()) return;
      const { section, version: v } = await createSection(
        projectId,
        { title: newSection.trim() },
        version,
      );
      if (v != null) setVersion(v);
      setSections((prev) => [...prev, section]);
      setCurrentId(section.id);
      setNewSection("");
    });

  const removeSection = (id: number) =>
    guard(async () => {
      const { version: v } = await deleteSection(projectId, id, version);
      if (v != null) setVersion(v);
      setSections((prev) => prev.filter((s) => s.id !== id));
      if (currentId === id) setCurrentId(null);
    });

  const addBlock = (sectionId: number, body: NewBlock) =>
    guard(async () => {
      const { block, version: v } = await createBlock(
        projectId,
        sectionId,
        body,
        version,
      );
      if (v != null) setVersion(v);
      setBlocks((prev) => [...prev, block]);
    });

  const removeBlock = (sectionId: number, blockId: number) =>
    guard(async () => {
      const { version: v } = await deleteBlock(
        projectId,
        sectionId,
        blockId,
        version,
      );
      if (v != null) setVersion(v);
      setBlocks((prev) => prev.filter((b) => b.id !== blockId));
    });

  if (authLoading) return <p className="text-sm text-black/60">Loading…</p>;
  if (!user)
    return (
      <p className="text-sm">
        <Link href="/login" className="underline underline-offset-4">
          Log in
        </Link>{" "}
        to edit.
      </p>
    );
  if (!project) {
    return error ? (
      <p className="text-sm text-red-600">{error}</p>
    ) : (
      <p className="text-sm text-black/60">Loading…</p>
    );
  }

  const isOwner = project.owner_id === user.id || user.role === "admin";
  if (!isOwner) {
    return (
      <p className="text-sm">
        You don&apos;t own this project.{" "}
        <Link
          href={`/projects/${projectId}`}
          className="underline underline-offset-4"
        >
          View it
        </Link>
        .
      </p>
    );
  }

  const current = sections.find((s) => s.id === currentId) ?? null;

  return (
    <div className="space-y-6">
      <div>
        <Link
          href={`/projects/${projectId}`}
          className="text-sm text-black/50 underline-offset-4 hover:underline dark:text-white/50"
        >
          ← View lesson
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">Editing: {project.name}</h1>
        <p className="text-sm text-black/50 dark:text-white/50">
          Version {version}
        </p>
      </div>

      {conflict && (
        <p className="rounded-lg border border-blue-500/40 bg-blue-500/10 px-3 py-2 text-sm">
          This project changed elsewhere — reloaded to the latest version. Please
          redo your last action.
        </p>
      )}
      {error && (
        <p className="rounded border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-300">
          {error}
        </p>
      )}

      <div className="grid grid-cols-1 gap-8 sm:grid-cols-[15rem_1fr]">
        {/* sections */}
        <div className="space-y-3">
          <div className="space-y-1">
            {sections.map((s, i) => (
              <div key={s.id} className="flex items-center gap-1">
                <button
                  onClick={() => setCurrentId(s.id)}
                  className={`flex-1 truncate rounded px-2 py-1.5 text-left text-sm ${
                    s.id === currentId
                      ? "bg-black/[0.06] font-medium dark:bg-white/10"
                      : "hover:bg-black/[0.03] dark:hover:bg-white/5"
                  }`}
                >
                  {i + 1}. {s.title ?? `Step ${i + 1}`}
                </button>
                <button
                  onClick={() => removeSection(s.id)}
                  title="Delete step"
                  className="rounded px-1.5 py-1 text-sm text-red-600 hover:bg-red-500/10"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
          <div className="flex gap-1">
            <input
              value={newSection}
              onChange={(e) => setNewSection(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addSection()}
              placeholder="New step title"
              className="min-w-0 flex-1 rounded border border-black/15 px-2 py-1.5 text-sm dark:border-white/20 dark:bg-transparent"
            />
            <button
              onClick={addSection}
              className="shrink-0 rounded bg-black px-2.5 py-1.5 text-sm font-medium text-white dark:bg-white dark:text-black"
            >
              +
            </button>
          </div>
        </div>

        {/* blocks of the current section */}
        <div className="min-w-0 space-y-4">
          {current == null ? (
            <p className="text-sm text-black/60">
              Select or add a step to edit its content.
            </p>
          ) : (
            <>
              <h2 className="text-lg font-semibold">
                {current.title ?? "Step"}
              </h2>
              {blocks.map((b) => (
                <div key={b.id} className="group relative">
                  <BlockView block={b} />
                  <button
                    onClick={() => removeBlock(current.id, b.id)}
                    title="Delete block"
                    className="absolute right-1 top-1 rounded bg-white/80 px-1.5 py-0.5 text-xs text-red-600 opacity-0 shadow-sm transition group-hover:opacity-100 dark:bg-black/60"
                  >
                    ✕
                  </button>
                </div>
              ))}
              <BlockForm onAdd={(body) => addBlock(current.id, body)} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
