export interface User {
  id: number;
  username: string;
}

export interface Conversation {
  id: number;
  user_id: number;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface FileItem {
  id: number;
  conversation_id: number;
  path: string;
  filename: string;
  original_filename: string;
  size: number;
}

export interface IngestionStatusData {
  id: string;
  file_id: number;
  conversation_id: number;
  status: 'queued' | 'processing' | 'cancelling' | 'cancelled' | 'completed' | 'failed';
  progress: number;
  stage: string | null;
  processed_chunks: number;
  total_chunks: number;
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface ChunkSource {
  chunk_id?: string;
  parent_id?: string;
  file_id?: number;
  filename?: string;
  heading_path?: string;
  content: string;
  parent_content?: string;
  score: number;
}

export interface MessageItem {
  id: number;
  conversation_id: number;
  user_id: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  sources?: ChunkSource[] | null;
  created_at: string;
}

export interface ChatRequest {
  message: string;
  top_k?: number;
  score_threshold?: number;
  temperature?: number;
  model?: string;
}
