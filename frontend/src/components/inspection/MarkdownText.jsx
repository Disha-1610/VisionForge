import React from 'react';
import ReactMarkdown from 'react-markdown';

/**
 * Translates academic / mathematical jargon (e.g. SSIM, MSE, raw machine codes) into plain English.
 */
export const simplifyJargon = (str) => {
  if (!str || typeof str !== 'string') return str;
  let s = str;

  // Translate "SSIM similarity 0.861 meets threshold 0.80"
  s = s.replace(/SSIM similarity\s+([0-9.]+)\s+meets threshold\s+([0-9.]+)/gi, (_, sim, thr) => {
    const simPct = (parseFloat(sim) * 100).toFixed(1);
    const thrPct = (parseFloat(thr) * 100).toFixed(0);
    return `Visual match: ${simPct}% (passing required standard ${thrPct}%)`;
  });

  // Translate "SSIM similarity 0.650 below threshold 0.80 (diff 15.0%, MSE 24.1)"
  s = s.replace(/SSIM similarity\s+([0-9.]+)\s+below threshold\s+([0-9.]+)(?:\s*\([^)]*\))?/gi, (_, sim, thr) => {
    const simPct = (parseFloat(sim) * 100).toFixed(1);
    const thrPct = (parseFloat(thr) * 100).toFixed(0);
    return `Visual difference detected: Match is only ${simPct}% (below required standard ${thrPct}%)`;
  });

  // Translate "match score 0.89 meets threshold 0.80"
  s = s.replace(/match score\s+([0-9.]+)\s+(?:meets|is above)\s+(?:expected\s+)?threshold\s+([0-9.]+)/gi, (_, score, thr) => {
    const scorePct = (parseFloat(score) * 100).toFixed(1);
    const thrPct = (parseFloat(thr) * 100).toFixed(0);
    return `Label match: ${scorePct}% (meets required standard ${thrPct}%)`;
  });

  // Translate "match score 0.65 is below expected threshold 0.80"
  s = s.replace(/match score\s+([0-9.]+)\s+is below expected threshold\s+([0-9.]+)/gi, (_, score, thr) => {
    const scorePct = (parseFloat(score) * 100).toFixed(1);
    const thrPct = (parseFloat(thr) * 100).toFixed(0);
    return `Label defect detected: Match is only ${scorePct}% (below required standard ${thrPct}%)`;
  });

  // Translate machine tags like "(gold_pin_connector: 0)"
  s = s.replace(/\(([a-z0-9_]+):\s*([0-9]+)\)/gi, (_, name, count) => {
    const cleanName = name.replace(/_/g, ' ');
    return `(${count} ${cleanName} verified)`;
  });

  // Clean raw diff/MSE references
  s = s.replace(/\(diff\s+[0-9.]+%\s*,\s*MSE\s+[0-9.]+\)/gi, '');

  return s;
};

/**
 * Automatically formats plain-text inspection narratives, explanations, or root-causes into clean structured Markdown.
 */
export const cleanAndStructureMarkdown = (raw) => {
  if (!raw) return '';
  let text = typeof raw === 'string' ? raw : typeof raw === 'object' ? JSON.stringify(raw) : String(raw);
  text = simplifyJargon(text.trim());

  // Strip contradictory prefix if description notes defect
  const hasDefectKeyword = /critical|missing|damage|scratch|corrosion|discrepanc|defect|tamper|counterfeit|peel/i.test(text);
  if (hasDefectKeyword && /no visible defect\s*—\s*/i.test(text)) {
    text = text.replace(/no visible defect\s*—\s*/gi, '');
  }

  // If text already has markdown bullets, line breaks, or headers, return directly
  if (text.includes('\n- ') || text.includes('\n* ') || text.includes('\n1.') || text.includes('### ') || text.includes('## ')) {
    return text;
  }

  // Extract Section/ROI Prefix (e.g., "General Module Surface: ..." or "CPU / Part ID Label: ...")
  let prefix = '';
  let body = text;
  const colonIdx = text.indexOf(': ');
  if (colonIdx > 0 && colonIdx < 45 && !text.slice(0, colonIdx).includes('\n')) {
    prefix = `**${text.substring(0, colonIdx).trim()}**\n\n`;
    body = text.substring(colonIdx + 2).trim();
  }

  // Semicolon separated statements (common in SSIM/hardware checks)
  if (body.includes('; ')) {
    const parts = body.split('; ').map((p) => p.trim()).filter(Boolean);
    const bullets = parts.map((p) => `- ${p}`).join('\n');
    return `${prefix}${bullets}`;
  }

  // Multiple sentences: turn into structured observations
  const sentences = body
    .split(/(?<=[.!?])\s+(?=[A-Z])/)
    .map((s) => s.trim())
    .filter(Boolean);

  if (sentences.length > 1) {
    const lead = sentences[0];
    const bulletItems = sentences
      .slice(1)
      .map((s) => {
        let formatted = s;
        if (/^in the golden reference/i.test(s)) {
          formatted = s.replace(/^in the golden reference/i, '**Golden Reference:** In the baseline');
        } else if (/^in the inspection sample/i.test(s)) {
          formatted = s.replace(/^in the inspection sample/i, '**Inspection Sample:** In test unit');
        } else if (/^additionally,/i.test(s)) {
          formatted = s.replace(/^additionally,\s*/i, '**Defect Found:** ');
        }
        return `- ${formatted}`;
      })
      .join('\n');

    return `${prefix}${lead}\n\n${bulletItems}`;
  }

  return `${prefix}${body}`;
};

export const MarkdownText = ({ text, className = '' }) => {
  if (!text) return null;
  const structuredMarkdown = cleanAndStructureMarkdown(text);

  return (
    <div className={`leading-relaxed text-slate-200 text-xs sm:text-[13px] ${className}`}>
      <ReactMarkdown
        components={{
          p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,
          strong: ({ children }) => (
            <strong className="font-bold text-cyan-300">{children}</strong>
          ),
          em: ({ children }) => (
            <em className="italic text-slate-300">{children}</em>
          ),
          h1: ({ children }) => (
            <h1 className="text-base font-bold text-white mb-2 pb-1 border-b border-hud-border font-telemetry uppercase tracking-wider">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-sm font-bold text-white mb-1.5 font-telemetry uppercase tracking-wider">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-xs font-bold text-cyan-300 mb-1 font-mono uppercase tracking-wider">
              {children}
            </h3>
          ),
          ul: ({ children }) => (
            <ul className="space-y-1.5 my-2 pl-1 text-slate-300">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal space-y-1.5 my-2 pl-4 text-slate-300 font-mono">{children}</ol>
          ),
          li: ({ children }) => (
            <li className="flex items-start gap-2 leading-relaxed">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-cyan-400 mt-1.5 shrink-0 shadow-sm shadow-cyan-400/50" />
              <span className="flex-1">{children}</span>
            </li>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-cyan-400 pl-3 py-1 my-2 bg-hud-card/50 text-slate-300 rounded-r-lg italic">
              {children}
            </blockquote>
          ),
          code: ({ children }) => (
            <code className="px-1.5 py-0.5 rounded bg-slate-900 border border-hud-border text-cyan-300 font-mono text-[11px]">
              {children}
            </code>
          ),
        }}
      >
        {structuredMarkdown}
      </ReactMarkdown>
    </div>
  );
};

export default MarkdownText;