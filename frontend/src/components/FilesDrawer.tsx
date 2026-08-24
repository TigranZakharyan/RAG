import React, { useEffect, useRef, useState } from 'react';
import type { FileItem, IngestionStatusData } from '../types';
import { fileApi } from '../api';
import {
  UploadCloud,
  FileText,
  Trash2,
  XCircle,
  Loader2,
  Database,
} from 'lucide-react';

interface FilesDrawerProps {
  conversationId: number;
  files: FileItem[];
  onFileUploaded: () => void;
  onFileDeleted: (fileId: number) => void;
}

export const FilesDrawer: React.FC<FilesDrawerProps> = ({
  conversationId,
  files,
  onFileUploaded,
  onFileDeleted,
}) => {
  const [uploading, setUploading] = useState(false);
  const [ingestionStatuses, setIngestionStatuses] = useState<Record<number, IngestionStatusData>>({});
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Poll ingestion progress for processing or queued jobs
  useEffect(() => {
    let interval: any = null;


    const fetchStatuses = async () => {
      for (const file of files) {
        try {
          const status = await fileApi.getStatus(file.id);
          setIngestionStatuses((prev) => ({
            ...prev,
            [file.id]: status as IngestionStatusData,
          }));
        } catch {
          // ignore if no ingestion record yet
        }
      }
    };

    if (files.length > 0) {
      fetchStatuses();
      interval = setInterval(fetchStatuses, 3000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [files]);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;

    setUploading(true);
    try {
      await fileApi.upload(conversationId, selectedFile);
      onFileUploaded();
    } catch (err: any) {
      alert(`Upload error: ${err.message}`);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleCancel = async (fileId: number) => {
    try {
      await fileApi.cancelIngestion(fileId);
      const status = await fileApi.getStatus(fileId);
      setIngestionStatuses((prev) => ({ ...prev, [fileId]: status as IngestionStatusData }));
    } catch (err: any) {
      alert(`Failed to cancel: ${err.message}`);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <aside className="files-drawer">
      <div className="drawer-header">
        <div className="drawer-title">
          <Database size={17} color="#818CF8" />
          <span>Knowledge Base</span>
        </div>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
          {files.length} document{files.length === 1 ? '' : 's'}
        </span>
      </div>

      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        style={{ display: 'none' }}
        accept=".pdf,.docx,.txt,.md,.xlsx,.pptx,.html"
      />

      <div
        id="upload-file-zone"
        className="file-upload-zone"
        onClick={() => fileInputRef.current?.click()}
      >
        {uploading ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
            <Loader2 size={24} className="animate-spin" color="#818CF8" />
            <span style={{ fontSize: '0.8rem', color: '#A5B4FC' }}>Uploading & chunking...</span>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
            <UploadCloud size={24} color="#818CF8" />
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#E0E7FF' }}>
              Upload Document
            </span>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>
              PDF, DOCX, TXT, MD, XLSX
            </span>
          </div>
        )}
      </div>

      <div className="drawer-files-list">
        {files.length === 0 ? (
          <div className="empty-state">
            <FileText size={32} style={{ opacity: 0.3 }} />
            <p style={{ fontSize: '0.8rem' }}>No documents uploaded yet for this conversation.</p>
          </div>
        ) : (
          files.map((file) => {
            const status = ingestionStatuses[file.id];
            const isProcessing = status?.status === 'processing' || status?.status === 'queued';

            return (
              <div key={file.id} id={`file-card-${file.id}`} className="file-card animate-fade-in">
                <div className="file-card-header">
                  <div className="file-meta">
                    <FileText size={16} color="#A5B4FC" style={{ flexShrink: 0 }} />
                    <div>
                      <div className="file-name" title={file.original_filename}>
                        {file.original_filename}
                      </div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>
                        {formatFileSize(file.size)}
                      </div>
                    </div>
                  </div>

                  <button
                    title="Delete document"
                    onClick={() => {
                      if (confirm(`Delete ${file.original_filename}?`)) {
                        onFileDeleted(file.id);
                      }
                    }}
                    style={{ color: '#F43F5E', padding: 4 }}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>

                {/* Progress / Status display */}
                {status && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span className={`status-badge status-${status.status}`}>
                        {status.status}
                      </span>
                      <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                        {status.stage ? `${status.stage} • ` : ''}
                        {status.progress}%
                      </span>
                    </div>

                    <div className="progress-bar-container">
                      <div
                        className="progress-bar-fill"
                        style={{ width: `${status.progress}%` }}
                      />
                    </div>

                    {isProcessing && (
                      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 2 }}>
                        <button
                          onClick={() => handleCancel(file.id)}
                          style={{
                            fontSize: '0.7rem',
                            color: '#FB7185',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 4,
                          }}
                        >
                          <XCircle size={12} />
                          Cancel Indexing
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
};
