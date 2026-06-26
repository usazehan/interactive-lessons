"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth";

export default function Nav() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();

  return (
    <header className="border-b border-black/10 dark:border-white/15">
      <nav className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
        <Link href="/" className="font-semibold">
          Interactive Lessons
        </Link>
        <div className="flex items-center gap-4 text-sm">
          {loading ? null : user ? (
            <>
              <span className="text-black/60 dark:text-white/60">
                {user.email}
                {!user.is_verified && " (unverified)"}
              </span>
              <button
                onClick={async () => {
                  await logout();
                  router.push("/");
                }}
                className="rounded border border-black/15 px-2 py-1 hover:bg-black/5 dark:border-white/20 dark:hover:bg-white/10"
              >
                Log out
              </button>
            </>
          ) : (
            <Link href="/login" className="underline underline-offset-4">
              Log in
            </Link>
          )}
        </div>
      </nav>
    </header>
  );
}
