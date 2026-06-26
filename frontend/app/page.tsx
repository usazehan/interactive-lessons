"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth";
import { createProject, listProjects, type Project } from "@/lib/api";

function NewProject() {
  const { user } = useAuth();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!user) return null;

  if (!user.is_verified) {
    return (
      <p className="text-sm text-black/50 dark:text-white/50">
        Verify your email to author lessons.
      </p>
    );
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="rounded bg-black px-4 py-2 text-sm font-medium text-white dark:bg-white dark:text-black"
      >
        + New lesson
      </button>
    );
  }

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const project = await createProject(name.trim(), description.trim() || undefined);
      router.push(`/projects/${project.id}/edit`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not create");
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={create}
      className="space-y-2 rounded-lg border border-black/10 p-3 dark:border-white/15"
    >
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        required
        placeholder="Lesson name"
        className="w-full rounded border border-black/15 px-2 py-1.5 text-sm dark:border-white/20 dark:bg-transparent"
      />
      <input
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Short description (optional)"
        className="w-full rounded border border-black/15 px-2 py-1.5 text-sm dark:border-white/20 dark:bg-transparent"
      />
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={busy || !name.trim()}
          className="rounded bg-black px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
        >
          Create
        </button>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="rounded border border-black/15 px-3 py-1.5 text-sm dark:border-white/20"
        >
          Cancel
        </button>
      </div>
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
    </form>
  );
}

export default function Home() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listProjects()
      .then(setProjects)
      .catch((e) => setError(e.message ?? "failed to load projects"));
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Lessons</h1>
          <p className="text-sm text-black/60 dark:text-white/60">
            Browse projects. Log in to author or to track your progress.
          </p>
        </div>
      </div>

      <NewProject />

      {error && (
        <p className="rounded border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-300">
          {error} — is the API running on{" "}
          <code>
            {process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}
          </code>
          ?
        </p>
      )}

      {projects === null && !error ? (
        <p className="text-sm text-black/60">Loading…</p>
      ) : projects && projects.length === 0 ? (
        <p className="text-sm text-black/60">No projects yet.</p>
      ) : (
        <ul className="divide-y divide-black/10 dark:divide-white/10">
          {projects?.map((p) => (
            <li key={p.id}>
              <Link
                href={`/projects/${p.id}`}
                className="-mx-2 block rounded px-2 py-3 hover:bg-black/[0.03] dark:hover:bg-white/5"
              >
                <div className="font-medium">{p.name}</div>
                {p.description && (
                  <div className="text-sm text-black/60 dark:text-white/60">
                    {p.description}
                  </div>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
