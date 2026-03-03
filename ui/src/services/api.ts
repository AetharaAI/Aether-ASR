import axios, { AxiosError } from 'axios';
import { Job, TranscriptionConfig, ModelInfo, Preset } from '../types';

// @ts-ignore
const API_BASE_URL = import.meta.env?.VITE_API_URL || '';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

const getOidcToken = () => {
  try {
    const oidcStorage = localStorage.getItem('oidc.user:https://passport.aetherpro.us/realms/aetherpro:aether-asr');
    if (oidcStorage) {
      const user = JSON.parse(oidcStorage);
      return user.access_token;
    }
  } catch (e) {
    console.error("Failed to parse OIDC token from storage", e);
  }
  return null;
};

// Add OIDC Token to requests
api.interceptors.request.use((config) => {
  const token = getOidcToken();
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }
  return config;
});

// Handle errors
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Token may be invalid/expired, let react-oidc-context handle refresh or login
      localStorage.removeItem('oidc.user:https://passport.aetherpro.us/realms/aetherpro:aether-asr');
      window.location.href = '/';
    }
    return Promise.reject(error);
  }
);

export const jobsApi = {
  createJob: async (file: File, config: TranscriptionConfig): Promise<Job> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('model', config.model);
    formData.append('language', config.language);
    formData.append('compute_type', config.compute_type);
    formData.append('vad_enabled', String(config.vad_enabled));
    formData.append('vad_threshold', String(config.vad_threshold));
    formData.append('diarization_enabled', String(config.diarization_enabled));
    formData.append('word_timestamps', String(config.word_timestamps));
    formData.append('chunk_length', String(config.chunk_length));
    formData.append('chunk_overlap', String(config.chunk_overlap));
    formData.append('output_format', config.output_format);
    formData.append('retention_days', String(config.retention_days));

    const response = await api.post('/api/transcriptions', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  listJobs: async (params?: { status?: string; limit?: number; offset?: number }): Promise<{ items: Job[]; pagination: any }> => {
    const response = await api.get('/api/transcriptions', { params });
    return response.data;
  },

  getJob: async (jobId: string): Promise<Job> => {
    const response = await api.get(`/api/transcriptions/${jobId}`);
    return response.data;
  },

  cancelJob: async (jobId: string): Promise<void> => {
    await api.post(`/api/transcriptions/${jobId}/cancel`);
  },

  downloadTranscript: async (jobId: string, format: string): Promise<Blob> => {
    const response = await api.get(`/api/transcriptions/${jobId}/download`, {
      params: { format },
      responseType: 'blob',
    });
    return response.data;
  },

  subscribeToEvents: (jobId: string, onEvent: (event: any) => void) => {
    const eventSource = new EventSource(`${API_BASE_URL}/api/transcriptions/${jobId}/events`);

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      onEvent(data);
    };

    eventSource.onerror = () => {
      eventSource.close();
    };

    return () => eventSource.close();
  },
};

export const modelsApi = {
  listModels: async (): Promise<ModelInfo[]> => {
    const response = await api.get('/api/models');
    return response.data.models;
  },
};

export const presetsApi = {
  listPresets: async (): Promise<Preset[]> => {
    const response = await api.get('/api/admin/presets');
    return response.data;
  },

  createPreset: async (preset: Omit<Preset, 'id'>): Promise<Preset> => {
    const response = await api.post('/api/admin/presets', preset);
    return response.data;
  },

  updatePreset: async (id: string, preset: Partial<Preset>): Promise<Preset> => {
    const response = await api.put(`/api/admin/presets/${id}`, preset);
    return response.data;
  },

  deletePreset: async (id: string): Promise<void> => {
    await api.delete(`/api/admin/presets/${id}`);
  },
};

export const healthApi = {
  checkHealth: async (): Promise<any> => {
    const response = await api.get('/api/health');
    return response.data;
  },

  getVersion: async (): Promise<any> => {
    const response = await api.get('/api/version');
    return response.data;
  },
};

export default api;
