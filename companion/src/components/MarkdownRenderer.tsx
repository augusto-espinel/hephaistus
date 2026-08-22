import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css' // KaTeX CSS for math rendering

interface MarkdownRendererProps {
  content: string
  className?: string
}

/**
 * Renders markdown content with:
 * - GitHub-flavored markdown (tables, strikethrough, task lists)
 * - LaTeX math ($inline$ and $$block$$)
 * - Syntax-highlighted code blocks
 */
export function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  return (
    <div className={`markdown-content ${className || ''}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          // Style code blocks
          code({ inline, className, children, ...props }: any) {
            return !inline ? (
              <code className={`code-block ${className || ''}`} {...props}>
                {children}
              </code>
            ) : (
              <code className="code-inline" {...props}>
                {children}
              </code>
            )
          },
          // Style tables
          table({ children }) {
            return <table className="markdown-table">{children}</table>
          },
          // Style headings
          h1({ children }) {
            return <h1 className="markdown-h1">{children}</h1>
          },
          h2({ children }) {
            return <h2 className="markdown-h2">{children}</h2>
          },
          h3({ children }) {
            return <h3 className="markdown-h3">{children}</h3>
          },
          h4({ children }) {
            return <h4 className="markdown-h4">{children}</h4>
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}