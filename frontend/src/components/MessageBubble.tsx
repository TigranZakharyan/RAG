import React, { useState } from 'react';
import type { MessageItem } from '../types';
import { Bot, User as UserIcon, BookOpen, ChevronDown, ChevronUp } from 'lucide-react';


interface MessageBubbleProps {
  message: MessageItem;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isUser = message.role === 'user';
  const [sourcesOpen, setSourcesOpen] = useState(false);

  return (
    <div className={`message-row ${isUser ? 'user' : 'ai'}`}>
      <div className={`msg-avatar ${isUser ? 'user' : 'ai'}`}>
        {isUser ? <UserIcon size={16} /> : <Bot size={18} />}
      </div>

      <div className={`msg-bubble ${isUser ? 'user' : 'ai'}`}>
        <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {message.content}
        </div>

        {/* Cited Sources & References */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="sources-card">
            <div
              className="sources-header"
              onClick={() => setSourcesOpen(!sourcesOpen)}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <BookOpen size={14} color="#818CF8" />
                <span>{message.sources.length} Cited Sources</span>
              </div>
              {sourcesOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </div>

            {sourcesOpen && (
              <div className="sources-list animate-fade-in">
                {message.sources.map((source, idx) => (
                  <div key={idx} className="source-item">
                    <div className="source-title">
                      <span>
                        [Doc {idx + 1}] {source.heading_path || source.filename || 'Context'}
                      </span>
                      <span className="source-score">
                        Match {Math.round(source.score * 100)}%
                      </span>
                    </div>
                    <div className="source-snippet">
                      {source.parent_content || source.content}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <div
          style={{
            fontSize: '0.675rem',
            color: isUser ? 'rgba(255,255,255,0.6)' : 'var(--text-dim)',
            marginTop: 6,
            textAlign: isUser ? 'right' : 'left',
          }}
        >
          {new Date(message.created_at).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </div>
      </div>
    </div>
  );
};
