import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { Job, TranscriptionConfig, ModelInfo, Preset } from '../types';

interface AppState {
  // Auth
  apiKey: string | null;
  setApiKey: (key: string | null) => void;

  // Jobs
  jobs: Job[];
  setJobs: (jobs: Job[]) => void;
  addJob: (job: Job) => void;
  updateJob: (jobId: string, updates: Partial<Job>) => void;

  // Models
  models: ModelInfo[];
  setModels: (models: ModelInfo[]) => void;

  // Presets
  presets: Preset[];
  setPresets: (presets: Preset[]) => void;

  // Default config
  defaultConfig: TranscriptionConfig;
  setDefaultConfig: (config: TranscriptionConfig) => void;

  // UI state
  isUploading: boolean;
  setIsUploading: (value: boolean) => void;
}

const defaultTranscriptionConfig: TranscriptionConfig = {
  model: 'base',
  language: 'auto',
  compute_type: 'float16',
  vad_enabled: true,
  vad_threshold: 0.5,
  diarization_enabled: false,
  word_timestamps: false,
  chunk_length: 30,
  chunk_overlap: 5,
  output_format: 'json',
  retention_days: 7,
};

export const useStore = create<AppState>()(
  persist(
    (set) => ({
      // Auth
      apiKey: null,
      setApiKey: (key) => set({ apiKey: key }),

      // Jobs
      jobs: [],
      setJobs: (jobs) => set({ jobs }),
      addJob: (job) => set((state) => ({ jobs: [job, ...state.jobs] })),
      updateJob: (jobId, updates) =>
        set((state) => ({
          jobs: state.jobs.map((j) =>
            j.id === jobId ? { ...j, ...updates } : j
          ),
        })),

      // Models
      models: [],
      setModels: (models) => set({ models }),

      // Presets
      presets: [],
      setPresets: (presets) => set({ presets }),

      // Default config
      defaultConfig: defaultTranscriptionConfig,
      setDefaultConfig: (config) => set({ defaultConfig: config }),

      // UI state
      isUploading: false,
      setIsUploading: (value) => set({ isUploading: value }),
    }),
    {
      name: 'asr-storage',
      partialize: (state) => ({
        apiKey: state.apiKey,
        defaultConfig: state.defaultConfig,
      }),
    }
  )
);
