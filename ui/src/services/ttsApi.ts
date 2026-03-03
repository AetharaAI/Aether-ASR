import axios from 'axios';

// @ts-ignore - Vite specific env vars
const TTS_BASE_URL = import.meta.env?.VITE_TTS_URL || 'https://tts.aetherpro.us';

const ttsApiClient = axios.create({
    baseURL: TTS_BASE_URL,
});

export const getPredefinedVoices = async () => {
    try {
        const response = await ttsApiClient.get('/get_predefined_voices');
        return response.data.voices || [];
    } catch (error) {
        console.error("Failed to fetch TTS voices:", error);
        return [];
    }
};

export interface TtsRequestParams {
    text: string;
    voice_mode?: 'predefined' | 'clone';
    predefined_voice_id?: string;
    output_format?: 'wav' | 'mp3' | 'opus';
}

export const generateTTS = async (params: TtsRequestParams) => {
    try {
        const response = await ttsApiClient.post('/tts', params, {
            responseType: 'blob' // Important: Expect audio blob back
        });
        return response.data; // This will be the Blob
    } catch (error) {
        console.error("Failed to generate TTS:", error);
        throw error;
    }
};

export default {
    getPredefinedVoices,
    generateTTS,
};
