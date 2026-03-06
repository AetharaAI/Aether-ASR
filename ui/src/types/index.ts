export interface Job {
  id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';
  created_at: string;
  started_at?: string;
  completed_at?: string;
  file_info?: {
    original_name?: string;
    storage_key?: string;
    size_bytes?: number;
    duration_seconds?: number;
    format?: string;
    sample_rate?: number;
    channels?: number;
  };
  config: TranscriptionConfig;
  progress: {
    percent: number;
    current_step: string;
    message: string;
  };
  result?: TranscriptionResult;
  error?: {
    code: string;
    message: string;
  };
  artifacts?: Record<string, string>;
}

export interface TranscriptionConfig {
  model: string;
  language: string;
  compute_type: 'float16' | 'int8' | 'float32';
  vad_enabled: boolean;
  vad_threshold: number;
  diarization_enabled: boolean;
  word_timestamps: boolean;
  chunk_length: number;
  chunk_overlap: number;
  output_format: 'json' | 'srt' | 'vtt' | 'txt';
  retention_days: number;
}

export interface TranscriptionResult {
  language: string;
  language_probability?: number;
  duration: number;
  text: string;
  segments: TranscriptSegment[];
  speakers?: string[];
}

export interface TranscriptSegment {
  id: number;
  start: number;
  end: number;
  text: string;
  speaker?: string;
  confidence?: number;
  words?: WordTimestamp[];
}

export interface WordTimestamp {
  word: string;
  start: number;
  end: number;
  confidence?: number;
}

export interface ModelInfo {
  id: string;
  name: string;
  description: string;
  parameters: string;
  languages: string[];
  capabilities: {
    transcription: boolean;
    translation: boolean;
    vad: boolean;
    diarization: boolean;
    word_timestamps: boolean;
  };
  resources: {
    vram_gb: number;
    compute_types: string[];
    relative_speed: number;
  };
}

export interface Preset {
  id: string;
  name: string;
  description?: string;
  config: TranscriptionConfig;
  is_default: boolean;
}
