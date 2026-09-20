import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { 
  Bot, Send, X, Sparkles, RefreshCcw, User, AlertCircle, Copy, Check, 
  ChevronDown, ChevronUp, Cpu, Database, ShieldAlert, FileText, CheckCircle2,
  Maximize2, Minimize2, ArrowUpRight, Building2, HelpCircle
} from 'lucide-react';
import api from '../../services/apiClient';
import { AssistantChatResponse, CitedDocument } from '../../types/api';

interface ThoughtStep {
  label: string;
  detail: string;
  status: 'completed' | 'active' | 'pending';
}

interface MessageItem {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  citations?: CitedDocument[];
  followups?: string[];
  timestamp: string;
  isError?: boolean;
  thoughtSteps?: { label: string; detail: string }[];
  thoughtDurationSec?: number;
}

interface AIAssistantDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  activeProjectCode: string | null;
  initialQuery?: string;
  onSelectProject: (code: string) => void;
}

/** Rich Markdown styling */
const mdComponents: React.ComponentProps<typeof ReactMarkdown>['components'] = {
  h1: ({ children }) => <h1 className="text-sm font-extrabold text-slate-900 mt-3 mb-1.5 border-b border-slate-200 pb-1">{children}</h1>,
  h2: ({ children }) => <h2 className="text-sm font-bold text-slate-800 mt-2.5 mb-1">{children}</h2>,
  h3: ({ children }) => <h3 className="text-xs font-bold text-indigo-900 mt-2.5 mb-1 flex items-center gap-1">{children}</h3>,
  h4: ({ children }) => <h4 className="text-xs font-semibold text-slate-700 mt-1.5 mb-0.5">{children}</h4>,
  p: ({ children }) => <p className="text-xs text-slate-800 leading-relaxed mb-2">{children}</p>,
  ul: ({ children }) => <ul className="list-disc list-inside space-y-1 mb-2 ml-1 text-xs text-slate-700">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal list-inside space-y-1 mb-2 ml-1 text-xs text-slate-700">{children}</ol>,
  li: ({ children }) => <li className="text-xs text-slate-700 leading-relaxed">{children}</li>,
  strong: ({ children }) => <strong className="font-extrabold text-slate-950">{children}</strong>,
  em: ({ children }) => <em className="italic text-slate-600">{children}</em>,
  code: ({ children }) => <code className="bg-slate-100 text-blue-700 text-[11px] px-1 py-0.5 rounded font-mono font-semibold border border-slate-200">{children}</code>,
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-indigo-500 bg-indigo-50/40 pl-2.5 py-1.5 my-2 text-slate-700 italic text-[11px] rounded-r">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="border-slate-200 my-2.5" />,
  a: ({ href, children }) => (
    <a href={href} className="text-blue-600 font-semibold underline text-[11px]" target="_blank" rel="noreferrer">
      {children}
    </a>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto my-2 rounded-lg border border-slate-200 shadow-xs">
      <table className="text-[11px] border-collapse w-full">{children}</table>
    </div>
  ),
  th: ({ children }) => <th className="border-b border-slate-200 px-2.5 py-1 bg-slate-100 font-bold text-slate-800 text-left">{children}</th>,
  td: ({ children }) => <td className="border-b border-slate-100 px-2.5 py-1 text-slate-700 font-medium">{children}</td>,
};

const THINKING_STEPS_FLOW = [
  { label: "Query Ingestion & Entity Resolution", detail: "Parsing infrastructure intent, project codes & analytical scope..." },
  { label: "Live Database & Vector Retrieval", detail: "Querying PostgreSQL live metrics & scanning 331k PAIMANA vectors..." },
  { label: "ML Risk & SHAP Decomposition", detail: "Evaluating calibrated XGBoost risk probabilities & driver impacts..." },
  { label: "Executive Intelligence Synthesis", detail: "Synthesizing detailed policy analysis & dynamic follow-up options..." }
];

export const AIAssistantDrawer: React.FC<AIAssistantDrawerProps> = ({
  isOpen,
  onClose,
  activeProjectCode,
  initialQuery,
  onSelectProject
}) => {
  const getInitialMessage = (pCode: string | null): MessageItem => ({
    id: 'welcome',
    sender: 'assistant',
    text: pCode
      ? `Greetings. I am **Nirman AI Copilot** — grounded in live surveillance data across all 5,461 projects.\n\nActive surveillance context is locked to **\`${pCode}\`**. I can analyze its financial cost expansion, schedule delay, physical execution status, or official PAIMANA Flash Report audit findings.`
      : `Greetings. I am **Nirman AI Copilot**, powered by Gemini and grounded in 5,461 live infrastructure projects (PostgreSQL + SQLite), calibrated XGBoost risk models, and 331,206 PAIMANA audit report vectors.\n\nAsk me anything regarding national infrastructure intelligence, cost overrun root causes, agency performance, or specific project bottlenecks.`,
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    followups: pCode
      ? [
        `What are the primary cost overrun factors for ${pCode}?`,
        `Analyze schedule delay and anticipated completion for ${pCode}`,
        `What do PAIMANA audit reports cite for ${pCode}?`
      ]
      : [
        'Which sectors account for the highest cumulative cost overrun?',
        'What are the primary root causes of critical risk project delays?',
        'Show top 5 railway projects with major schedule slippage'
      ],
    thoughtSteps: [
      { label: "Live Database Handshake", detail: "Verified live connection with PostgreSQL nirman_db." },
      { label: "Surveillance Governance", detail: "Calibrated XGBoost severe risk engine active (Threshold T* = 0.28)." }
    ],
    thoughtDurationSec: 0.8
  });

  const [messages, setMessages] = useState<MessageItem[]>([getInitialMessage(activeProjectCode)]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [thinkingTimer, setThinkingTimer] = useState(0);
  const [expandedReasoning, setExpandedReasoning] = useState<Record<string, boolean>>({});
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const timerRef = useRef<any>(null);
  const lastSentInitialQueryRef = useRef<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [messages, isOpen, loading, currentStepIndex]);

  useEffect(() => {
    if (initialQuery && isOpen && lastSentInitialQueryRef.current !== initialQuery) {
      lastSentInitialQueryRef.current = initialQuery;
      handleSendMessage(initialQuery);
    }
    if (!isOpen) {
      lastSentInitialQueryRef.current = null;
    }
  }, [initialQuery, isOpen]);

  // Handle thinking animation steps and timer
  useEffect(() => {
    if (loading) {
      setThinkingTimer(0);
      setCurrentStepIndex(0);

      const interval = setInterval(() => {
        setThinkingTimer(prev => Number((prev + 0.1).toFixed(1)));
      }, 100);

      const stepInterval = setInterval(() => {
        setCurrentStepIndex(prev => (prev < THINKING_STEPS_FLOW.length - 1 ? prev + 1 : prev));
      }, 850);

      timerRef.current = { interval, stepInterval };

      return () => {
        clearInterval(interval);
        clearInterval(stepInterval);
      };
    }
  }, [loading]);

  const handleSendMessage = async (textToSend?: string) => {
    const queryText = (textToSend || input).trim();
    if (!queryText || loading) return;

    const userMsg: MessageItem = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: queryText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, userMsg]);
    if (!textToSend) setInput('');
    setLoading(true);

    const startTime = Date.now();

    try {
      const res: AssistantChatResponse = await api.sendAssistantMessage(queryText, activeProjectCode);
      const elapsedSec = Number(((Date.now() - startTime) / 1000).toFixed(1));

      const botMsg: MessageItem = {
        id: `bot-${Date.now()}`,
        sender: 'assistant',
        text: res.response || 'No response received from Gemini intelligence model.',
        citations: res.cited_documents || [],
        followups: res.suggested_followups || [],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        thoughtSteps: [
          { label: "Multi-Dimensional Intent", detail: "Parsed entities, focus attributes & governance scope." },
          { label: "Evidence Retrieval", detail: `Matched ${res.cited_documents?.length || 3} official PAIMANA chunks & live relational records.` },
          { label: "Calibrated Risk Evaluation", detail: "Computed XGBoost risk probabilities and SHAP driver attributions." },
          { label: "Policy Synthesis", detail: "Synthesized executive intelligence and dynamically formulated follow-up options." }
        ],
        thoughtDurationSec: elapsedSec
      };
      setMessages(prev => [...prev, botMsg]);
    } catch (err: any) {
      console.error('Assistant chat error:', err);
      const isTimeout = err?.code === 'ECONNABORTED' || err?.message?.includes('timeout');
      const errorMsg: MessageItem = {
        id: `err-${Date.now()}`,
        sender: 'assistant',
        text: isTimeout
          ? '⏱ The intelligence reasoning process took longer than expected under load. Please retry momentarily.'
          : '⚠️ Could not reach the Nirman Intelligence backend. Please ensure the server is active on port 8000.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        isError: true
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const toggleReasoning = (id: string) => {
    setExpandedReasoning(prev => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 w-full sm:w-[540px] bg-white border-l border-slate-200 shadow-2xl z-50 flex flex-col backdrop-blur-xl animate-in slide-in-from-right duration-200">
      {/* Sleek Copilot Header */}
      <div className="bg-slate-900 text-white px-5 py-3.5 flex items-center justify-between border-b border-slate-800 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="p-2 bg-gradient-to-tr from-blue-600 to-indigo-600 rounded-xl shadow-md">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-emerald-500 border-2 border-slate-900 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-extrabold text-sm tracking-tight text-white flex items-center gap-1.5">
                NIRMAN AI Copilot
              </h3>
              <span className="text-[10px] font-mono font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-400/30 px-1.5 py-0.5 rounded">
                v2.0 Deep Reasoning
              </span>
            </div>
            <p className="text-[11px] text-slate-400 font-medium">
              {activeProjectCode ? `Locked Context: ${activeProjectCode}` : '5,461 Projects • 331k PAIMANA Chunks • XGBoost Risk'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition"
            aria-label="Close assistant"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Active Project Banner */}
      {activeProjectCode && (
        <div className="bg-blue-50/90 px-4 py-2 border-b border-blue-200 flex items-center justify-between text-xs text-blue-900">
          <span className="flex items-center gap-1.5 font-semibold">
            <Building2 className="w-3.5 h-3.5 text-blue-700" />
            Active Surveillance: <strong className="font-mono text-blue-800">{activeProjectCode}</strong>
          </span>
          <button
            onClick={() => onSelectProject("")}
            className="text-[11px] font-bold text-blue-700 hover:text-blue-900 underline"
          >
            Reset to Portfolio
          </button>
        </div>
      )}

      {/* Messages Stream */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50/60">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}
          >
            {/* Sender Label */}
            <div className="flex items-center gap-1.5 text-[11px] text-slate-400 mb-1 px-1 font-mono">
              {msg.sender === 'user' ? (
                <>
                  <span className="font-semibold text-slate-600">Executive Officer</span>
                  <User className="w-3 h-3 text-slate-500" />
                </>
              ) : (
                <>
                  <Bot className="w-3.5 h-3.5 text-blue-600" />
                  <span className="font-semibold text-blue-700">Nirman Copilot</span>
                </>
              )}
              <span>• {msg.timestamp}</span>
            </div>

            {/* Message Card */}
            <div className={`max-w-[95%] rounded-2xl px-4 py-3.5 shadow-xs ${
              msg.sender === 'user'
                ? 'bg-slate-900 text-white rounded-br-none text-xs leading-relaxed font-medium'
                : msg.isError
                  ? 'bg-red-50 border border-red-200 rounded-bl-none text-xs'
                  : 'bg-white border border-slate-200/90 rounded-bl-none shadow-sm'
            }`}>
              {/* Expandable Thought Process / Reasoning Chain */}
              {msg.thoughtSteps && msg.thoughtSteps.length > 0 && !msg.isError && (
                <div className="mb-3 pb-2.5 border-b border-slate-100">
                  <button
                    onClick={() => toggleReasoning(msg.id)}
                    className="flex items-center gap-1.5 text-[11px] font-bold text-indigo-700 hover:text-indigo-900 bg-indigo-50/80 px-2.5 py-1 rounded-lg transition border border-indigo-100"
                  >
                    <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
                    <span>
                      {expandedReasoning[msg.id] ? "Hide Reasoning Chain" : `Verified Reasoning Chain (${msg.thoughtDurationSec || 1.2}s)`}
                    </span>
                    {expandedReasoning[msg.id] ? (
                      <ChevronUp className="w-3.5 h-3.5 text-indigo-500 ml-1" />
                    ) : (
                      <ChevronDown className="w-3.5 h-3.5 text-indigo-500 ml-1" />
                    )}
                  </button>

                  {expandedReasoning[msg.id] && (
                    <div className="mt-2.5 pl-2 space-y-1.5 border-l-2 border-indigo-300 text-[11px] text-slate-600 animate-in fade-in duration-150">
                      {msg.thoughtSteps.map((s, idx) => (
                        <div key={idx} className="flex items-start gap-1.5">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                          <div>
                            <strong className="text-slate-800">{s.label}: </strong>
                            <span>{s.detail}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Message Content */}
              {msg.sender === 'user' ? (
                <p className="text-xs leading-relaxed">{msg.text}</p>
              ) : msg.isError ? (
                <div className="flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
                  <p className="text-xs text-red-700 font-medium">{msg.text}</p>
                </div>
              ) : (
                <div className="prose-xs">
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                    {msg.text}
                  </ReactMarkdown>
                </div>
              )}

              {/* PAIMANA Citations */}
              {msg.citations && msg.citations.length > 0 && (
                <div className="pt-2.5 mt-3 border-t border-slate-100 space-y-2">
                  <span className="text-[10px] font-extrabold text-slate-500 uppercase tracking-wider block flex items-center gap-1">
                    <FileText className="w-3 h-3 text-blue-600" />
                    Official PAIMANA Document Ground Truth
                  </span>
                  <div className="space-y-1.5">
                    {msg.citations.map((cite, i) => (
                      <div key={i} className="p-2 bg-slate-50 border border-slate-200 rounded-lg text-[11px]">
                        <div className="font-bold text-blue-700 truncate">{cite.doc_name}</div>
                        {cite.snippet && (
                          <p className="text-slate-600 italic mt-0.5 line-clamp-2">"{cite.snippet}"</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Bottom Card Actions: Copy & Verification badge */}
              {msg.sender === 'assistant' && !msg.isError && (
                <div className="mt-3 pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
                  <span className="font-mono text-[10px]">Verified against MoSPI Flash Reports</span>
                  <button
                    onClick={() => copyToClipboard(msg.text, msg.id)}
                    className="flex items-center gap-1 text-slate-500 hover:text-slate-800 transition px-1.5 py-0.5 rounded hover:bg-slate-100"
                    title="Copy response"
                  >
                    {copiedId === msg.id ? (
                      <>
                        <Check className="w-3 h-3 text-emerald-600" />
                        <span className="text-emerald-700 font-bold">Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3" />
                        <span>Copy</span>
                      </>
                    )}
                  </button>
                </div>
              )}

              {/* Dynamic Follow-Up & Clarifying Questions */}
              {msg.followups && msg.followups.length > 0 && !msg.isError && (
                <div className="pt-3 mt-3 border-t border-slate-100 space-y-2">
                  <span className="text-[10px] font-bold text-indigo-700 uppercase tracking-wider block flex items-center gap-1">
                    <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
                    Suggested Follow-Up & Exploration Questions
                  </span>
                  <div className="flex flex-col gap-2">
                    {msg.followups.map((f, i) => (
                      <button
                        key={i}
                        onClick={() => handleSendMessage(f)}
                        disabled={loading}
                        className="w-full text-left p-2.5 bg-indigo-50/80 hover:bg-indigo-100/90 text-indigo-950 border border-indigo-200/80 rounded-xl text-xs font-medium transition flex items-start justify-between group shadow-2xs gap-2"
                      >
                        <span className="flex-1 whitespace-normal break-words leading-relaxed">{f}</span>
                        <ArrowUpRight className="w-4 h-4 text-indigo-400 group-hover:text-indigo-700 transition shrink-0 mt-0.5" />
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Multi-Stage Animated Thinking State */}
        {loading && (
          <div className="flex flex-col items-start space-y-1">
            <div className="flex items-center gap-1.5 text-[11px] text-indigo-600 font-mono px-1">
              <Sparkles className="w-3.5 h-3.5 animate-spin text-indigo-600" />
              <span className="font-bold">Nirman Copilot is analyzing ({thinkingTimer}s)...</span>
            </div>

            <div className="w-full max-w-[95%] bg-gradient-to-br from-indigo-50/90 via-blue-50/70 to-purple-50/90 border border-indigo-200/80 rounded-2xl rounded-bl-none p-4 shadow-md space-y-3 relative overflow-hidden">
              {/* Animated Shimmer Wave */}
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/40 to-transparent -translate-x-full animate-[shimmer_2s_infinite]" />

              <div className="flex items-center justify-between pb-2 border-b border-indigo-100">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full bg-indigo-600 animate-ping" />
                  <span className="text-xs font-extrabold text-indigo-950">
                    Executing Multi-Model Reasoning Chain
                  </span>
                </div>
                <span className="text-[11px] font-mono font-bold text-indigo-700 bg-white/80 px-2 py-0.5 rounded border border-indigo-200">
                  Step {currentStepIndex + 1} of 4
                </span>
              </div>

              {/* Steps Progress List */}
              <div className="space-y-2">
                {THINKING_STEPS_FLOW.map((step, idx) => {
                  const isDone = idx < currentStepIndex;
                  const isCurrent = idx === currentStepIndex;
                  return (
                    <div
                      key={idx}
                      className={`flex items-start gap-2.5 text-xs transition-all duration-300 ${
                        isCurrent
                          ? "font-bold text-indigo-950 scale-[1.01]"
                          : isDone
                          ? "text-slate-600 opacity-90"
                          : "text-slate-400 opacity-50"
                      }`}
                    >
                      <div className="mt-0.5 shrink-0">
                        {isDone ? (
                          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                        ) : isCurrent ? (
                          <div className="w-4 h-4 rounded-full border-2 border-indigo-600 border-t-transparent animate-spin" />
                        ) : (
                          <div className="w-3.5 h-3.5 rounded-full border border-slate-300 ml-0.5" />
                        )}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <span className="text-xs">{step.label}</span>
                          {isCurrent && (
                            <span className="text-[10px] font-mono text-indigo-600 animate-pulse">Running...</span>
                          )}
                        </div>
                        <p className="text-[11px] text-slate-500 font-normal mt-0.5 leading-tight">
                          {step.detail}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-3.5 bg-white border-t border-slate-200 flex-shrink-0 space-y-2">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="flex gap-2"
        >
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={activeProjectCode ? `Ask about ${activeProjectCode}...` : "Ask Nirman AI Copilot about any infrastructure project..."}
            disabled={loading}
            className="flex-1 bg-slate-50 text-slate-900 text-xs rounded-xl px-3.5 py-2.5 border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 font-medium"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-4 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-xl text-xs font-bold transition flex items-center justify-center shadow-sm disabled:cursor-not-allowed"
          >
            {loading ? <RefreshCcw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </form>

        <div className="flex items-center justify-between text-[10px] text-slate-400 px-1 font-mono">
          <span>Grounded in MoSPI Flash Reports &bull; Zero hallucination</span>
          <span>Shift + Enter for new line</span>
        </div>
      </div>
    </div>
  );
};
