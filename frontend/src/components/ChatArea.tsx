import React, { useEffect, useRef, useState } from 'react';
import type { Conversation, FileItem, MessageItem } from '../types';
import { chatApi } from '../api';
import { MessageBubble } from './MessageBubble';
import {
  Send,
  Sliders,
  Sparkles,
  Zap,
  Clock,
  Loader2,
  Trash2,
  Paperclip,
} from 'lucide-react';


interface ChatAreaProps {
  conversation: Conversation;
  files: FileItem[];
  onToggleFiles: () => void;
  showFiles: boolean;
}

export const ChatArea: React.FC<ChatAreaProps> = ({
  conversation,
  files,
  onToggleFiles,
  showFiles,
}) => {
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [isAsyncSubmitting, setIsAsyncSubmitting] = useState(false);
  const [currentStreamingText, setCurrentStreamingText] = useState('');
  const [currentStreamingSources, setCurrentStreamingSources] = useState<any[]>([]);

  // RAG Query controls
  const [topK, setTopK] = useState(5);
  const [temperature, setTemperature] = useState(0.2);
  const [showConfig, setShowConfig] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadMessages = async () => {
    try {
      const data = await chatApi.getMessages(conversation.id);
      setMessages(data);
    } catch (err) {
      console.error('Failed to load messages', err);
    }
  };

  useEffect(() => {
    loadMessages();
  }, [conversation.id]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentStreamingText]);

  // Handle Send with Real-Time SSE Stream
  const handleSendStream = async () => {
    if (!input.trim() || isStreaming) return;

    const userText = input.trim();
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    // Append optimistic user message
    const tempUserMsg: MessageItem = {
      id: Date.now(),
      conversation_id: conversation.id,
      user_id: conversation.user_id,
      role: 'user',
      content: userText,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, tempUserMsg]);
    setIsStreaming(true);
    setCurrentStreamingText('');
    setCurrentStreamingSources([]);

    await chatApi.streamChat(
      conversation.id,
      {
        message: userText,
        top_k: topK,
        temperature,
      },
      {
        onSources: (sources) => {
          setCurrentStreamingSources(sources);
        },
        onToken: (token) => {
          setCurrentStreamingText((prev) => prev + token);
        },
        onDone: () => {
          setIsStreaming(false);
          setCurrentStreamingText('');
          setCurrentStreamingSources([]);
          loadMessages();
        },

        onError: (err) => {
          setIsStreaming(false);
          alert(`Stream error: ${err.message}`);
          loadMessages();
        },
      }
    );
  };

  // Handle Send via Background Celery Task
  const handleSendAsync = async () => {
    if (!input.trim() || isStreaming || isAsyncSubmitting) return;

    const userText = input.trim();
    setInput('');
    setIsAsyncSubmitting(true);

    try {
      await chatApi.sendAsync(conversation.id, userText, topK);
      // Wait a moment and reload messages
      setTimeout(() => {
        loadMessages();
        setIsAsyncSubmitting(false);
      }, 2500);
    } catch (err: any) {
      alert(`Async error: ${err.message}`);
      setIsAsyncSubmitting(false);
    }
  };

  const handleClearHistory = async () => {
    if (confirm('Clear chat history for this conversation?')) {
      await chatApi.clearMessages(conversation.id);
      setMessages([]);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendStream();
    }
  };

  const handleInputResize = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
  };

  return (
    <div className="chat-panel">
      {/* Top Conversation Header */}
      <header className="top-nav">
        <div className="nav-title-section">
          <span className="nav-conversation-title">{conversation.title}</span>
        </div>

        <div className="nav-actions">
          <button
            id="toggle-config-btn"
            className={`action-pill-btn ${showConfig ? 'active' : ''}`}
            onClick={() => setShowConfig(!showConfig)}
          >
            <Sliders size={14} />
            <span>RAG Config</span>
          </button>

          <button
            id="toggle-files-btn"
            className={`action-pill-btn ${showFiles ? 'active' : ''}`}
            onClick={onToggleFiles}
          >
            <Paperclip size={14} />
            <span>Documents ({files.length})</span>
          </button>

          <button
            id="clear-chat-btn"
            className="action-pill-btn"
            onClick={handleClearHistory}
            title="Clear Chat History"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </header>

      {/* Optional RAG Parameters Config Bar */}
      {showConfig && (
        <div
          className="animate-fade-in"
          style={{
            padding: '10px 24px',
            background: 'rgba(0,0,0,0.3)',
            borderBottom: '1px solid var(--border-subtle)',
            display: 'flex',
            alignItems: 'center',
            gap: 24,
            fontSize: '0.8rem',
            color: 'var(--text-muted)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>Top-K Chunks: {topK}</span>
            <input
              type="range"
              min="1"
              max="15"
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>Temperature: {temperature}</span>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={temperature}
              onChange={(e) => setTemperature(Number(e.target.value))}
            />
          </div>
        </div>
      )}

      {/* Messages List Area */}
      <div className="messages-container">
        {messages.length === 0 && !isStreaming ? (
          <div className="empty-state">
            <div className="avatar" style={{ width: 48, height: 48 }}>
              <Sparkles size={24} />
            </div>
            <h3 style={{ color: '#E0E7FF', fontWeight: 600 }}>Ask your documents</h3>
            <p style={{ maxWidth: 460, fontSize: '0.875rem' }}>
              Upload PDF or text documents into the knowledge drawer on the right. Your query will
              perform dense & BM25 sparse hybrid retrieval to stream precise, cited answers.
            </p>
          </div>
        ) : (
          messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)
        )}

        {/* Real-Time Live Streaming Bubble */}
        {isStreaming && (
          <MessageBubble
            message={{
              id: 999999,
              conversation_id: conversation.id,
              user_id: conversation.user_id,
              role: 'assistant',
              content: currentStreamingText || 'Extracting chunks & thinking...',
              sources: currentStreamingSources,
              created_at: new Date().toISOString(),
            }}
          />
        )}

        {isAsyncSubmitting && (
          <div className="message-row ai animate-fade-in">
            <div className="msg-avatar ai">
              <Loader2 size={16} className="animate-spin" />
            </div>
            <div className="msg-bubble ai" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Clock size={16} color="#818CF8" />
              <span>Background task submitted to Celery worker...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Chat Input Bar */}
      <div className="input-panel">
        <div className="input-box-wrapper">
          <textarea
            ref={textareaRef}
            id="chat-input-textarea"
            className="chat-textarea"
            placeholder="Ask a question about your documents... (Press Enter to send)"
            value={input}
            onChange={handleInputResize}
            onKeyDown={handleKeyDown}
            rows={1}
          />

          <div className="input-actions-bar">
            <div className="input-config-chips">
              <span className="config-chip">Top {topK} Chunks</span>
              <span className="config-chip">Hybrid RRF</span>
              <span className="config-chip">Ollama Stream</span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <button
                id="send-async-btn"
                title="Send as Background Celery Task"
                onClick={handleSendAsync}
                disabled={!input.trim() || isStreaming || isAsyncSubmitting}
                style={{
                  padding: '6px 10px',
                  borderRadius: 'var(--radius-md)',
                  background: 'rgba(255,255,255,0.06)',
                  color: 'var(--text-muted)',
                  fontSize: '0.75rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                }}
              >
                <Zap size={13} color="#FBBF24" />
                <span>Background</span>
              </button>

              <button
                id="send-chat-btn"
                className="send-btn"
                onClick={handleSendStream}
                disabled={!input.trim() || isStreaming}
                title="Stream Answer (Enter)"
              >
                {isStreaming ? <Loader2 size={18} className="animate-spin" /> : <Send size={16} />}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
