const API_BASE = '';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}


async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('token');
  const headers: HeadersInit = {
    ...options.headers,
  };

  if (token) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (!response.ok) {
    let errorDetail = response.statusText;
    try {
      const errorJson = await response.json();
      errorDetail = errorJson.detail || errorJson.message || errorDetail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, errorDetail);
  }

  if (response.status === 204) {
    return null as unknown as T;
  }

  return response.json();
}

// ----------------------------------------------------
// AUTH API
// ----------------------------------------------------
export const authApi = {
  login: async (username: string, password: string) => {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    const data = await request<{ access_token: string; token_type: string }>('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData.toString(),
    });

    if (data.access_token) {
      localStorage.setItem('token', data.access_token);
    }
    return data;
  },

  register: async (username: string, password: string) => {
    return request<{ id: number; username: string }>('/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
  },

  getMe: async () => {
    return request<{ id: number; username: string }>('/users/me');
  },

  logout: async () => {
    try {
      await request('/auth/logout', { method: 'POST' });
    } finally {
      localStorage.removeItem('token');
    }
  },
};

// ----------------------------------------------------
// CONVERSATIONS API
// ----------------------------------------------------
export const conversationApi = {
  list: async () => {
    const res = await request<{ conversations: Array<{ id: number; user_id: number; title: string; created_at: string; updated_at: string }> }>('/conversations/');
    return res.conversations;
  },

  create: async (title: string) => {
    return request<{ id: number; user_id: number; title: string; created_at: string; updated_at: string }>('/conversations/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    });
  },

  update: async (conversationId: number, title: string) => {
    return request<{ id: number; user_id: number; title: string; created_at: string; updated_at: string }>(`/conversations/${conversationId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    });
  },

  delete: async (conversationId: number) => {
    return request<null>(`/conversations/${conversationId}`, {
      method: 'DELETE',
    });
  },
};

// ----------------------------------------------------
// FILES & INGESTION API
// ----------------------------------------------------
export const fileApi = {
  listByConversation: async (conversationId: number) => {
    const res = await request<{ files: Array<{ id: number; conversation_id: number; path: string; filename: string; original_filename: string; size: number }> }>(`/files/conversation/${conversationId}`);
    return res.files;
  },

  upload: async (conversationId: number, file: File) => {
    const formData = new FormData();
    formData.append('file', file);

    const token = localStorage.getItem('token');
    const headers: HeadersInit = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const res = await fetch(`/files/${conversationId}`, {
      method: 'POST',
      headers,
      credentials: 'include',
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(err.detail || 'Upload failed');
    }

    return res.json();
  },

  getStatus: async (fileId: number) => {
    return request<{
      id: string;
      file_id: number;
      conversation_id: number;
      status: string;
      progress: number;
      stage: string | null;
      processed_chunks: number;
      total_chunks: number;
      error: string | null;
      created_at: string;
    }>(`/files/${fileId}/ingestion`);
  },

  cancelIngestion: async (fileId: number) => {
    return request<{ id: string; status: string }>(`/files/${fileId}/ingestion/cancel`, {
      method: 'POST',
    });
  },

  delete: async (fileId: number) => {
    return request<{ message: string }>(`/files/${fileId}`, {
      method: 'DELETE',
    });
  },
};

// ----------------------------------------------------
// CHAT API & SSE STREAMING
// ----------------------------------------------------
export const chatApi = {
  getMessages: async (conversationId: number) => {
    const res = await request<{ messages: Array<any> }>(`/chat/${conversationId}/messages`);
    return res.messages;
  },

  clearMessages: async (conversationId: number) => {
    return request<null>(`/chat/${conversationId}/messages`, {
      method: 'DELETE',
    });
  },

  sendAsync: async (conversationId: number, message: string, top_k = 5) => {
    return request<{ task_id: string; status: string; conversation_id: number }>(`/chat/${conversationId}/async`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, top_k }),
    });
  },

  streamChat: async (
    conversationId: number,
    payload: { message: string; top_k?: number; score_threshold?: number; temperature?: number; model?: string },
    callbacks: {
      onSources?: (sources: any[]) => void;
      onToken?: (token: string) => void;
      onDone?: (info: any) => void;
      onError?: (err: Error) => void;
    }
  ) => {
    const token = localStorage.getItem('token');
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    try {
      const response = await fetch(`/chat/${conversationId}/stream`, {
        method: 'POST',
        headers,
        credentials: 'include',
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`Chat stream request failed: ${response.statusText}`);
      }

      if (!response.body) {
        throw new Error('ReadableStream not supported in this browser.');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const block of lines) {
          if (!block.trim()) continue;

          let eventType = 'message';
          let dataStr = '';

          for (const line of block.split('\n')) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith('data: ')) {
              dataStr = line.slice(6).trim();
            }
          }

          if (dataStr) {
            try {
              const parsed = JSON.parse(dataStr);
              if (eventType === 'sources' && callbacks.onSources) {
                callbacks.onSources(parsed.sources || []);
              } else if (eventType === 'token' && callbacks.onToken) {
                callbacks.onToken(parsed.token || '');
              } else if (eventType === 'done' && callbacks.onDone) {
                callbacks.onDone(parsed);
              }
            } catch (err) {
              console.error('Error parsing SSE block', err, dataStr);
            }
          }
        }
      }
    } catch (err) {
      if (callbacks.onError) {
        callbacks.onError(err as Error);
      }
    }
  },
};
