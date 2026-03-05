import api from './api';

export interface TtsVoice {
    name: string;
    filename: string;
}

export interface TtsRequestParams {
    text: string;
    voice_mode?: 'predefined' | 'clone';
    predefined_voice_id?: string;
    output_format?: 'wav' | 'mp3' | 'opus';
    temperature?: number;
    exaggeration?: number;
    speed_factor?: number;
    seed?: number;
}

export const getPredefinedVoices = async (): Promise<TtsVoice[]> => {
    try {
        const response = await api.get('/api/tts/voices');
        // The upstream returns an array of objects with name/filename
        const data = response.data;
        if (Array.isArray(data)) {
            return data.map((v: any) => ({
                name: v.name || v.filename || v,
                filename: v.filename || v.name || v,
            }));
        }
        return [];
    } catch (error) {
        console.error("Failed to fetch TTS voices:", error);
        return [];
    }
};

export const getTtsModelInfo = async () => {
    try {
        const response = await api.get('/api/tts/model-info');
        return response.data;
    } catch (error) {
        console.error("Failed to fetch TTS model info:", error);
        return null;
    }
};

export const getTtsHealth = async () => {
    try {
        const response = await api.get('/api/tts/health');
        return response.data;
    } catch (error) {
        return { status: 'unreachable' };
    }
};

export const generateTTS = async (params: TtsRequestParams): Promise<Blob> => {
    const response = await api.post('/api/tts/speech', params, {
        responseType: 'blob'
    });
    return response.data;
};

export default {
    getPredefinedVoices,
    getTtsModelInfo,
    getTtsHealth,
    generateTTS,
};
