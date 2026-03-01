"""ASR Pipeline using faster-whisper."""
import os
import tempfile
from typing import Callable, Optional, List, Dict, Any
import structlog

from app.utils.gpu_manager import GPUPool


logger = structlog.get_logger()


class ASRPipeline:
    """Complete ASR pipeline with VAD, chunking, and transcription."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model_name = config.get("model", "base")
        self.language = config.get("language", "auto")
        self.compute_type = config.get("compute_type", "float16")
        self.vad_enabled = config.get("vad_enabled", True)
        self.vad_threshold = config.get("vad_threshold", 0.5)
        self.diarization_enabled = config.get("diarization_enabled", False)
        self.word_timestamps = config.get("word_timestamps", False)
        self.chunk_length = config.get("chunk_length", 30)
        self.chunk_overlap = config.get("chunk_overlap", 5)
        
    def process(
        self,
        audio_path: str,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Run the full transcription pipeline."""
        
        def report(step: str, percent: int, **kwargs):
            if progress_callback:
                progress_callback(step, percent, **kwargs)
        
        # Step 1: VAD (optional)
        if self.vad_enabled:
            report("vad", 15)
            segments = self._run_vad(audio_path)
        else:
            segments = None
        
        # Step 2: Chunking
        report("chunking", 25, segments_count=len(segments) if segments else 1)
        chunks = self._create_chunks(audio_path, segments)
        
        # Step 3: Transcription
        all_segments = []
        chunk_offsets = []
        
        model = GPUPool.get_model(self.model_name, self.compute_type)
        
        for i, chunk in enumerate(chunks):
            percent = 30 + int((i / len(chunks)) * 50)
            report(
                "transcribing",
                percent,
                chunks_processed=i,
                chunks_total=len(chunks)
            )
            
            result = self._transcribe_chunk(model, chunk)
            all_segments.extend(result.get("segments", []))
            chunk_offsets.append(chunk.get("offset", 0))
        
        # Step 4: Diarization (optional)
        if self.diarization_enabled:
            report("diarization", 85)
            all_segments = self._run_diarization(audio_path, all_segments)
        
        # Step 5: Merge and format
        report("formatting", 95)
        merged_segments = self._merge_segments(all_segments, chunk_offsets)
        
        # Build result
        full_text = " ".join([s.get("text", "").strip() for s in merged_segments])
        
        result = {
            "language": self.language if self.language != "auto" else "en",
            "language_probability": 1.0,
            "duration": merged_segments[-1].get("end", 0) if merged_segments else 0,
            "text": full_text,
            "segments": merged_segments
        }
        
        # Add speakers if diarization was used
        if self.diarization_enabled:
            speakers = list(set(
                s.get("speaker") for s in merged_segments if s.get("speaker")
            ))
            result["speakers"] = speakers
        
        return result
    
    def _run_vad(self, audio_path: str) -> List[Dict[str, Any]]:
        """Run VAD to detect speech segments."""
        try:
            import torch
            import numpy as np
            from pydub import AudioSegment
            
            # Load audio
            audio = AudioSegment.from_file(audio_path)
            audio = audio.set_frame_rate(16000).set_channels(1)
            
            # Load Silero VAD
            model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=False
            )
            
            get_speech_timestamps = utils[0]
            
            # Convert to tensor
            wav = torch.from_numpy(
                np.array(audio.get_array_of_samples(), dtype=np.float32) / 32768.0
            )
            
            # Get speech timestamps
            speech_timestamps = get_speech_timestamps(
                wav,
                model,
                threshold=self.vad_threshold,
                sampling_rate=16000,
                min_speech_duration_ms=250,
                min_silence_duration_ms=500,
                speech_pad_ms=100
            )
            
            # Convert to segments
            segments = []
            for ts in speech_timestamps:
                start = ts['start'] / 16000
                end = ts['end'] / 16000
                segments.append({
                    "start": start,
                    "end": end,
                    "duration": end - start
                })
            
            return segments
            
        except Exception as e:
            logger.warning("vad_failed", error=str(e))
            return None
    
    def _create_chunks(
        self,
        audio_path: str,
        vad_segments: Optional[List[Dict]]
    ) -> List[Dict[str, Any]]:
        """Create audio chunks for processing."""
        from pydub import AudioSegment
        
        audio = AudioSegment.from_file(audio_path)
        audio = audio.set_frame_rate(16000).set_channels(1)
        
        chunks = []
        
        if vad_segments:
            # Use VAD segments
            for seg in vad_segments:
                start_ms = int(seg["start"] * 1000)
                end_ms = int(seg["end"] * 1000)
                
                segment_audio = audio[start_ms:end_ms]
                
                # Split long segments
                max_duration_ms = self.chunk_length * 1000
                overlap_ms = self.chunk_overlap * 1000
                
                if len(segment_audio) <= max_duration_ms:
                    chunks.append({
                        "audio": segment_audio,
                        "offset": seg["start"],
                        "duration": seg["duration"]
                    })
                else:
                    # Split into overlapping chunks
                    chunk_start = 0
                    while chunk_start < len(segment_audio):
                        chunk_end = min(chunk_start + max_duration_ms, len(segment_audio))
                        chunk_audio = segment_audio[chunk_start:chunk_end]
                        
                        chunks.append({
                            "audio": chunk_audio,
                            "offset": seg["start"] + (chunk_start / 1000),
                            "duration": len(chunk_audio) / 1000
                        })
                        
                        chunk_start += max_duration_ms - overlap_ms
        else:
            # No VAD - use fixed-size chunks
            chunk_ms = self.chunk_length * 1000
            overlap_ms = self.chunk_overlap * 1000
            
            start_ms = 0
            while start_ms < len(audio):
                end_ms = min(start_ms + chunk_ms, len(audio))
                chunk_audio = audio[start_ms:end_ms]
                
                chunks.append({
                    "audio": chunk_audio,
                    "offset": start_ms / 1000,
                    "duration": len(chunk_audio) / 1000
                })
                
                start_ms += chunk_ms - overlap_ms
        
        return chunks
    
    def _transcribe_chunk(
        self,
        model,
        chunk: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Transcribe a single chunk."""
        from pydub import AudioSegment
        
        # Save chunk to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            chunk["audio"].export(tmp.name, format="wav")
            tmp_path = tmp.name
        
        try:
            # Transcribe with faster-whisper
            segments, info = model.transcribe(
                tmp_path,
                language=self.language if self.language != "auto" else None,
                beam_size=self.config.get("beam_size", 5),
                best_of=self.config.get("best_of", 5),
                temperature=self.config.get("temperature", 0.0),
                condition_on_previous_text=True,
                word_timestamps=self.word_timestamps,
                vad_filter=False,  # We already did VAD
            )
            
            # Convert segments
            result_segments = []
            for segment in segments:
                seg_dict = {
                    "id": segment.id,
                    "start": segment.start + chunk.get("offset", 0),
                    "end": segment.end + chunk.get("offset", 0),
                    "text": segment.text.strip(),
                    "confidence": segment.avg_logprob,
                    "no_speech_prob": segment.no_speech_prob
                }
                
                if self.word_timestamps and segment.words:
                    seg_dict["words"] = [
                        {
                            "word": word.word.strip(),
                            "start": word.start + chunk.get("offset", 0),
                            "end": word.end + chunk.get("offset", 0),
                            "confidence": word.probability
                        }
                        for word in segment.words
                    ]
                
                result_segments.append(seg_dict)
            
            return {
                "language": info.language,
                "language_probability": info.language_probability,
                "segments": result_segments
            }
            
        finally:
            os.unlink(tmp_path)
    
    def _run_diarization(
        self,
        audio_path: str,
        segments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Run speaker diarization."""
        try:
            from pyannote.audio import Pipeline
            
            pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization")
            
            diarization = pipeline(audio_path)
            
            # Assign speakers to segments
            for seg in segments:
                seg_start = seg.get("start", 0)
                seg_end = seg.get("end", 0)
                
                # Find overlapping speaker
                best_speaker = None
                best_overlap = 0
                
                for turn, _, speaker in diarization.itertracks(yield_label=True):
                    overlap_start = max(seg_start, turn.start)
                    overlap_end = min(seg_end, turn.end)
                    overlap = max(0, overlap_end - overlap_start)
                    
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_speaker = speaker
                
                if best_speaker:
                    seg["speaker"] = best_speaker
            
            return segments
            
        except Exception as e:
            logger.warning("diarization_failed", error=str(e))
            return segments
    
    def _merge_segments(
        self,
        segments: List[Dict[str, Any]],
        chunk_offsets: List[float]
    ) -> List[Dict[str, Any]]:
        """Merge segments from multiple chunks."""
        if not segments:
            return []
        
        # Sort by start time
        segments = sorted(segments, key=lambda s: s.get("start", 0))
        
        # Merge close segments with same speaker
        merged = []
        current = segments[0].copy()
        
        for next_seg in segments[1:]:
            gap = next_seg.get("start", 0) - current.get("end", 0)
            same_speaker = current.get("speaker") == next_seg.get("speaker")
            
            # Merge if gap is small (< 0.5s) and same speaker
            if gap < 0.5 and same_speaker:
                current["end"] = next_seg.get("end", current["end"])
                current["text"] = current.get("text", "") + " " + next_seg.get("text", "")
                current["confidence"] = (current.get("confidence", 0) + next_seg.get("confidence", 0)) / 2
                
                if "words" in current and "words" in next_seg:
                    current["words"].extend(next_seg["words"])
            else:
                merged.append(current)
                current = next_seg.copy()
        
        merged.append(current)
        
        # Renumber segments
        for i, seg in enumerate(merged):
            seg["id"] = i
        
        return merged
