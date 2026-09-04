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
 * - Collapsible JSON code blocks (click to expand/collapse)
 * - Collapsible thinking/reasoning blocks
 */
export function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  return (
    <div className={`markdown-content ${className || ''}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          // Make fenced code blocks collapsible (especially JSON)
          pre({ children, ...props }) {
            // Check if the child is a code block with json class
            const child = Array.isArray(children) ? children[0] : children
            const isJsonBlock = child?.props?.className?.includes('language-json')
            const isLongBlock = child?.props?.children && 
              String(child.props.children).length > 200
            
            if (isJsonBlock || isLongBlock) {
              const langLabel = isJsonBlock ? 'JSON' : 'Code'
              const charCount = child?.props?.children 
                ? String(child.props.children).length 
                : 0
              return (
                <details className="collapsible-code-block" open>
                  <summary>
                    {isJsonBlock ? '📋' : '💻'} {langLabel} 
                    {charCount > 0 && ` (${charCount} chars)`}
                  </summary>
                  <pre {...props}>{children}</pre>
                </details>
              )
            }
            
            return <pre {...props}>{children}</pre>
          },
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
