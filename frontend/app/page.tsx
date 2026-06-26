"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { listProjects, type Project } from "@/lib/api";

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
      <div>
        <h1 className="text-2xl font-semibold">Lessons</h1>
        <p className="text-sm text-black/60 dark:text-white/60">
          Browse projects. Log in to author or to track your progress.
        </p>
      </div>

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
