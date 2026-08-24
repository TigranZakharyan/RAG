import React, { useState } from 'react';
import type { Conversation } from '../types';
import { useAuth } from '../context/AuthContext';
import {
  MessageSquarePlus,
  MessageSquare,
  Trash2,
  Edit2,
  Check,
  X,
  LogOut,
  Sparkles,
} from 'lucide-react';


interface SidebarProps {
  conversations: Conversation[];
  activeId: number | null;
  onSelect: (id: number) => void;
  onCreate: (title: string) => void;
  onUpdate: (id: number, title: string) => void;
  onDelete: (id: number) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  conversations,
  activeId,
  onSelect,
  onCreate,
  onUpdate,
  onDelete,
}) => {
  const { user, logout } = useAuth();
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState('');

  const handleStartEdit = (c: Conversation, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(c.id);
    setEditTitle(c.title);
  };

  const handleSaveEdit = (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (editTitle.trim()) {
      onUpdate(id, editTitle.trim());
    }
    setEditingId(null);
  };

  const handleCancelEdit = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(null);
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="brand-logo">
          <Sparkles size={20} color="#818CF8" />
          <span>RAG AI</span>
          <span className="brand-badge">OLLAMA</span>
        </div>
      </div>

      <button
        id="new-chat-btn"
        className="new-chat-btn"
        onClick={() => onCreate('New Conversation')}
      >
        <MessageSquarePlus size={18} />
        <span>New Chat</span>
      </button>

      <div className="conversations-list">
        {conversations.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '30px 10px', color: 'var(--text-dim)', fontSize: '0.8rem' }}>
            No conversations yet. Create one to begin!
          </div>
        ) : (
          conversations.map((c) => {
            const isActive = c.id === activeId;
            const isEditing = c.id === editingId;

            return (
              <div
                key={c.id}
                id={`conversation-${c.id}`}
                className={`conversation-item ${isActive ? 'active' : ''}`}
                onClick={() => onSelect(c.id)}
              >
                <div className="conversation-title-wrapper">
                  <MessageSquare size={16} style={{ flexShrink: 0, opacity: isActive ? 1 : 0.6 }} />
                  {isEditing ? (
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                      style={{
                        background: 'rgba(0,0,0,0.5)',
                        border: '1px solid var(--accent-primary)',
                        borderRadius: 4,
                        padding: '2px 6px',
                        fontSize: '0.825rem',
                        color: 'white',
                        width: '100%',
                      }}
                      autoFocus
                    />
                  ) : (
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.title}</span>
                  )}
                </div>

                <div className="conversation-actions">
                  {isEditing ? (
                    <>
                      <button
                        title="Save title"
                        onClick={(e) => handleSaveEdit(c.id, e)}
                        style={{ color: '#10B981', padding: 2 }}
                      >
                        <Check size={14} />
                      </button>
                      <button
                        title="Cancel edit"
                        onClick={handleCancelEdit}
                        style={{ color: '#94A3B8', padding: 2 }}
                      >
                        <X size={14} />
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        title="Rename"
                        onClick={(e) => handleStartEdit(c, e)}
                        style={{ color: 'var(--text-dim)', padding: 2 }}
                      >
                        <Edit2 size={13} />
                      </button>
                      <button
                        title="Delete conversation"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (confirm('Delete this conversation and its data?')) {
                            onDelete(c.id);
                          }
                        }}
                        style={{ color: '#F43F5E', padding: 2 }}
                      >
                        <Trash2 size={13} />
                      </button>
                    </>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      <div className="sidebar-user">
        <div className="user-info">
          <div className="avatar">
            {user?.username?.charAt(0).toUpperCase() || 'U'}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>{user?.username}</span>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>Online • Ollama Local</span>
          </div>
        </div>

        <button
          id="logout-btn"
          title="Sign out"
          onClick={logout}
          style={{ color: 'var(--text-dim)', padding: 6, borderRadius: 6 }}
        >
          <LogOut size={16} />
        </button>
      </div>
    </aside>
  );
};
