"use client";

import { useState } from "react";

import type { BlockType, NewBlock } from "@/lib/api";

const TYPES: { value: BlockType; label: string }[] = [
  { value: "text", label: "Text (Markdown)" },
  { value: "code_block", label: "Code block" },
  { value: "image", label: "Image" },
  { value: "checkpoint", label: "Checkpoint" },
];

const input =
  "w-full rounded border border-black/15 px-2 py-1.5 text-sm dark:border-white/20 dark:bg-transparent";

// Builds a NewBlock payload appropriate to the selected type and hands it up.
export default function BlockForm({
  onAdd,
}: {
  onAdd: (block: NewBlock) => Promise<void>;
}) {
  const [type, setType] = useState<BlockType>("text");
  const [textContent, setTextContent] = useState("");
  const [codeContent, setCodeContent] = useState("");
  const [language, setLanguage] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [alt, setAlt] = useState("");
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);

  function build(): NewBlock | null {
    switch (type) {
      case "text":
        return textContent.trim()
          ? { type, text_content: textContent }
          : null;
      case "code_block":
        return codeContent.trim()
          ? {
              type,
              code_content: codeContent,
              keyword_metadata: language.trim() || undefined,
            }
          : null;
      case "image":
        return imageUrl.trim()
          ? {
              type,
              image_url: imageUrl.trim(),
              keyword_metadata: alt.trim() || undefined,
            }
          : null;
      case "checkpoint":
        return title.trim() ? { type, title: title.trim() } : null;
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const body = build();
    if (!body) return;
    setBusy(true);
    try {
      await onAdd(body);
      setTextContent("");
      setCodeContent("");
      setLanguage("");
      setImageUrl("");
      setAlt("");
      setTitle("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="space-y-2 rounded-lg border border-black/10 p-3 dark:border-white/15"
    >
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium">Add block</span>
        <select
          value={type}
          onChange={(e) => setType(e.target.value as BlockType)}
          className="rounded border border-black/15 px-2 py-1 text-sm dark:border-white/20 dark:bg-transparent"
        >
          {TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      </div>

      {type === "text" && (
        <textarea
          value={textContent}
          onChange={(e) => setTextContent(e.target.value)}
          placeholder="Markdown — links, `inline code`, **bold**…"
          rows={4}
          className={input}
        />
      )}
      {type === "code_block" && (
        <>
          <textarea
            value={codeContent}
            onChange={(e) => setCodeContent(e.target.value)}
            placeholder="code…"
            rows={4}
            className={`${input} font-mono`}
          />
          <input
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            placeholder="language (optional, e.g. bash)"
            className={input}
          />
        </>
      )}
      {type === "image" && (
        <>
          <input
            value={imageUrl}
            onChange={(e) => setImageUrl(e.target.value)}
            placeholder="https://image-url"
            className={input}
          />
          <input
            value={alt}
            onChange={(e) => setAlt(e.target.value)}
            placeholder="alt text (optional)"
            className={input}
          />
        </>
      )}
      {type === "checkpoint" && (
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="checkpoint title"
          className={input}
        />
      )}

      <button
        type="submit"
        disabled={busy}
        className="rounded bg-black px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
      >
        Add
      </button>
    </form>
  );
}
