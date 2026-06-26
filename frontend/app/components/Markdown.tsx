import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Markdown rendered with Tailwind-styled elements (no typography plugin needed).
export default function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: (props) => <p className="leading-7" {...props} />,
        a: (props) => (
          <a
            className="text-blue-600 underline underline-offset-2 hover:text-blue-700 dark:text-blue-400"
            target="_blank"
            rel="noreferrer"
            {...props}
          />
        ),
        ul: (props) => <ul className="list-disc space-y-1 pl-6" {...props} />,
        ol: (props) => <ol className="list-decimal space-y-1 pl-6" {...props} />,
        h1: (props) => <h1 className="text-xl font-semibold" {...props} />,
        h2: (props) => <h2 className="text-lg font-semibold" {...props} />,
        h3: (props) => <h3 className="font-semibold" {...props} />,
        blockquote: (props) => (
          <blockquote
            className="border-l-2 border-black/20 pl-3 text-black/70 dark:border-white/20 dark:text-white/70"
            {...props}
          />
        ),
        code: (props) => (
          <code
            className="rounded bg-black/5 px-1 py-0.5 font-mono text-[0.85em] dark:bg-white/10"
            {...props}
          />
        ),
      }}
    >
      {children}
    </ReactMarkdown>
  );
}
