import type { ContentBlock } from "@/lib/api";

import Markdown from "./Markdown";

// Renders one content block by type. Inline links / inline code live inside
// `text` blocks' Markdown; `code_block` is a standalone fenced block.
export default function BlockView({ block }: { block: ContentBlock }) {
  switch (block.type) {
    case "text":
      return (
        <div className="text-[15px] text-black/80 dark:text-white/80">
          <Markdown>{block.text_content ?? ""}</Markdown>
        </div>
      );

    case "code_block":
      return (
        <div className="overflow-hidden rounded-lg border border-black/10 dark:border-white/15">
          {block.keyword_metadata && (
            <div className="border-b border-black/10 bg-black/[0.03] px-3 py-1 font-mono text-xs text-black/50 dark:border-white/15 dark:bg-white/5 dark:text-white/50">
              {block.keyword_metadata}
            </div>
          )}
          <pre className="overflow-x-auto bg-black/[0.02] p-3 dark:bg-white/5">
            <code className="font-mono text-sm">{block.code_content}</code>
          </pre>
        </div>
      );

    case "image":
      return (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={block.image_url ?? ""}
          alt={block.keyword_metadata ?? ""}
          className="max-h-96 rounded-lg border border-black/10 dark:border-white/15"
        />
      );

    case "checkpoint":
      return (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-4">
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-400">
            Checkpoint
          </div>
          <div className="font-medium">{block.checkpoint?.title}</div>
        </div>
      );

    default:
      return null;
  }
}
