interface ContextViewProps {
  layers: Record<string, string>
}

export function ContextView({ layers }: ContextViewProps) {
  return (
    <div className="context-view">
      <h3>Context Layers</h3>
      <div className="layers">
        {Object.entries(layers).map(([name, content]) => (
          <LayerSection key={name} name={name} content={content} />
        ))}
      </div>
    </div>
  )
}

interface LayerSectionProps {
  name: string
  content: string
}

function LayerSection({ name, content }: LayerSectionProps) {
  const [expanded, setExpanded] = useState(true)

  return (
    <div className={`layer-section layer-${name}`}>
      <div className="layer-header" onClick={() => setExpanded(!expanded)}>
        <span className="expand-icon">{expanded ? '▼' : '▶'}</span>
        <span className="layer-title">{name.charAt(0).toUpperCase() + name.slice(1)} Layer</span>
        <span className="layer-size">{content.length.toLocaleString()} chars</span>
      </div>
      {expanded && (
        <pre className="layer-content">{content}</pre>
      )}
    </div>
  )
}

import { useState } from 'react'