import React, { useEffect, useState } from 'react';
import type { Conversation, FileItem } from './types';
import { conversationApi, fileApi } from './api';
import { useAuth } from './context/AuthContext';
import { AuthModal } from './components/AuthModal';
import { Sidebar } from './components/Sidebar';
import { ChatArea } from './components/ChatArea';
import { FilesDrawer } from './components/FilesDrawer';
import { Bot, MessageSquarePlus, Sparkles } from 'lucide-react';

export const App: React.FC = () => {
  const { user, loading } = useAuth();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [files, setFiles] = useState<FileItem[]>([]);
  const [showFiles, setShowFiles] = useState<boolean>(true);


  // Load all user conversations
  const loadConversations = async () => {
    if (!user) return;
    try {
      const list = await conversationApi.list();
      setConversations(list);
      if (list.length > 0 && (!activeId || !list.find((c) => c.id === activeId))) {
        setActiveId(list[0].id);
      }
    } catch (err) {
      console.error('Failed to load conversations', err);
    }
  };


  // Load files for the active conversation
  const loadFiles = async (conversationId: number) => {
    try {
      const data = await fileApi.listByConversation(conversationId);
      setFiles(data);
    } catch (err) {
      console.error('Failed to load files', err);
    }
  };

  useEffect(() => {
    if (user) {
      loadConversations();
    }
  }, [user]);

  useEffect(() => {
    if (activeId) {
      loadFiles(activeId);
    } else {
      setFiles([]);
    }
  }, [activeId]);

  const handleCreateConversation = async (title: string) => {
    try {
      const newConv = await conversationApi.create(title);
      setConversations((prev) => [newConv, ...prev]);
      setActiveId(newConv.id);
    } catch (err) {
      console.error('Failed to create conversation', err);
    }
  };

  const handleUpdateConversation = async (id: number, title: string) => {
    try {
      const updated = await conversationApi.update(id, title);
      setConversations((prev) => prev.map((c) => (c.id === id ? updated : c)));
    } catch (err) {
      console.error('Failed to update conversation', err);
    }
  };

  const handleDeleteConversation = async (id: number) => {
    try {
      await conversationApi.delete(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (activeId === id) {
        const remaining = conversations.filter((c) => c.id !== id);
        setActiveId(remaining.length > 0 ? remaining[0].id : null);
      }
    } catch (err) {
      console.error('Failed to delete conversation', err);
    }
  };

  if (loading) {
    return (
      <div className="auth-wrapper">
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
          <div className="avatar" style={{ width: 44, height: 44 }}>
            <Sparkles size={22} className="animate-spin" />
          </div>
          <span style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Initializing workspace...
          </span>
        </div>
      </div>
    );
  }

  if (!user) {
    return <AuthModal />;
  }

  const activeConversation = conversations.find((c) => c.id === activeId);

  return (
    <div className="app-container">
      {/* Left Sidebar */}
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={setActiveId}
        onCreate={handleCreateConversation}
        onUpdate={handleUpdateConversation}
        onDelete={handleDeleteConversation}
      />

      {/* Main Content Workspace */}
      <main className="main-content">
        {activeConversation ? (
          <div className="workspace-body">
            <ChatArea
              conversation={activeConversation}
              files={files}
              onToggleFiles={() => setShowFiles(!showFiles)}
              showFiles={showFiles}
            />

            {showFiles && (
              <FilesDrawer
                conversationId={activeConversation.id}
                files={files}
                onFileUploaded={() => loadFiles(activeConversation.id)}
                onFileDeleted={async (fileId) => {
                  try {
                    await fileApi.delete(fileId);
                    setFiles((prev) => prev.filter((f) => f.id !== fileId));
                    loadFiles(activeConversation.id);
                  } catch (err: any) {
                    alert(`Failed to delete file: ${err.message || 'Unknown error'}`);
                  }
                }}
              />

            )}
          </div>
        ) : (
          <div className="empty-state">
            <div className="avatar" style={{ width: 56, height: 56 }}>
              <Bot size={28} />
            </div>
            <h2 style={{ color: '#E0E7FF', fontWeight: 600 }}>Welcome to RAG AI</h2>
            <p style={{ maxWidth: 400, fontSize: '0.9rem' }}>
              Create or select a conversation to upload documents and begin chatting with Ollama in real-time.
            </p>
            <button
              id="create-first-chat-btn"
              className="new-chat-btn"
              onClick={() => handleCreateConversation('New Project')}
              style={{ marginTop: 8 }}
            >
              <MessageSquarePlus size={16} />
              <span>Create New Conversation</span>
            </button>
          </div>
        )}
      </main>
    </div>
  );
};
export default App;
