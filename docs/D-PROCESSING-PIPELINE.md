# ASR Service - Processing Pipeline Specification

## Pipeline Overview

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│  INPUT   │──▶│   VAD    │──▶│  CHUNK   │──▶│   ASR    │──▶│   POST   │──▶│  OUTPUT  │
│  AUDIO   │   │  (Silero)│   │  ENGINE  │   │ (Whisper)│   │  PROCESS │   │  FORMAT  │
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
     │              │              │              │              │              │
     │              │              │              │              │              │
     ▼              ▼              ▼              ▼              ▼              ▼
  Validate    Detect speech   Split into    Transcribe    Merge seg-    Export to
  format      segments        chunks with   each chunk    ments, add    SRT/VTT/
  Check       Remove silence  overlap       (GPU)         speaker       JSON/TXT
  duration    Threshold:      Max 30s       Beam size:    labels,       Store to
  Decode      0.5 default     Overlap: 5s   5 default     word-level    MinIO
  to WAV      Min duration:                                timestamps
              0.5s
```

---

## Stage 1: Input Validation & Decoding

### Supported Formats

| Format | Extension | MIME Type | Max Duration |
|--------|-----------|-----------|--------------|
| MP3 | .mp3 | audio/mpeg | 2 hours |
| WAV | .wav | audio/wav | 2 hours |
| M4A/AAC | .m4a, .aac | audio/mp4 | 2 hours |
| OGG | .ogg | audio/ogg | 2 hours |
| FLAC | .flac | audio/flac | 2 hours |
| WEBM | .webm | audio/webm | 2 hours |
| OPUS | .opus | audio/opus | 2 hours |

### Validation Steps

```python
class InputValidator:
    def validate(self, file_bytes: bytes, filename: str) -> ValidationResult:
        # 1. Check magic numbers (not just extension)
        magic = file_bytes[:8]
        detected_format = self.detect_format(magic)
        
        # 2. Validate extension matches content
        ext = Path(filename).suffix.lower()
        if not self.extension_matches_content(ext, detected_format):
            raise ValidationError("File extension does not match content")
        
        # 3. Check file size
        if len(file_bytes) > self.max_file_size:
            raise ValidationError(f"File exceeds {self.max_file_size} bytes")
        
        # 4. Decode to check integrity
        try:
            audio = AudioSegment.from_file(BytesIO(file_bytes))
        except Exception as e:
            raise ValidationError(f"Cannot decode audio: {e}")
        
        # 5. Check duration
        duration_ms = len(audio)
        if duration_ms > self.max_duration_ms:
            raise ValidationError(f"Audio exceeds {self.max_duration_ms}ms")
        
        # 6. Normalize to standard format
        normalized = self.normalize(audio)
        
        return ValidationResult(
            format=detected_format,
            duration_ms=duration_ms,
            sample_rate=normalized.frame_rate,
            channels=normalized.channels,
            normalized_audio=normalized
        )
    
    def normalize(self, audio: AudioSegment) -> AudioSegment:
        # Convert to mono, 16kHz, 16-bit PCM (Whisper requirement)
        return (audio
            .set_channels(1)
            .set_frame_rate(16000)
            .set_sample_width(2))
```

### Normalized Output Format
- **Sample Rate**: 16,000 Hz (Whisper requirement)
- **Channels**: Mono (1)
- **Bit Depth**: 16-bit PCM
- **Format**: WAV (intermediate processing)

---

## Stage 2: Voice Activity Detection (VAD)

### Silero VAD Configuration

```python
class VADProcessor:
    def __init__(self, 
                 model_path: str = "silero_vad",
                 threshold: float = 0.5,
                 min_speech_duration_ms: int = 250,
                 min_silence_duration_ms: int = 500,
                 speech_pad_ms: int = 100):
        
        self.model, self.utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False
        )
        self.threshold = threshold
        self.min_speech_duration_ms = min_speech_duration_ms
        self.min_silence_duration_ms = min_silence_duration_ms
        self.speech_pad_ms = speech_pad_ms
        
    def process(self, audio: AudioSegment) -> List[SpeechSegment]:
        """
        Returns list of speech segments with timestamps.
        """
        # Convert to tensor
        wav = torch.from_numpy(
            np.array(audio.get_array_of_samples(), dtype=np.float32) / 32768.0
        )
        
        # Get speech timestamps
        get_speech_timestamps = self.utils[0]
        
        speech_timestamps = get_speech_timestamps(
            wav,
            self.model,
            threshold=self.threshold,
            sampling_rate=audio.frame_rate,
            min_speech_duration_ms=self.min_speech_duration_ms,
            min_silence_duration_ms=self.min_silence_duration_ms,
            speech_pad_ms=self.speech_pad_ms
        )
        
        # Convert to segments
        segments = []
        for ts in speech_timestamps:
            start_ms = int(ts['start'] / audio.frame_rate * 1000)
            end_ms = int(ts['end'] / audio.frame_rate * 1000)
            
            segment_audio = audio[start_ms:end_ms]
            
            segments.append(SpeechSegment(
                start_ms=start_ms,
                end_ms=end_ms,
                duration_ms=end_ms - start_ms,
                audio=segment_audio,
                confidence=self._get_segment_confidence(wav, ts)
            ))
        
        return segments
    
    def _get_segment_confidence(self, wav: torch.Tensor, 
                                 ts: dict) -> float:
        """Calculate average speech probability for segment."""
        segment = wav[ts['start']:ts['end']]
        
        # Run VAD on segment
        with torch.no_grad():
            speech_probs = []
            window_size_samples = 512
            
            for i in range(0, len(segment), window_size_samples):
                chunk = segment[i:i + window_size_samples]
                if len(chunk) < window_size_samples:
                    break
                speech_prob = self.model(chunk, 16000).item()
                speech_probs.append(speech_prob)
            
            return sum(speech_probs) / len(speech_probs) if speech_probs else 0.0
```

### VAD Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `threshold` | 0.5 | 0.0 - 1.0 | Speech probability threshold |
| `min_speech_duration_ms` | 250 | 0 - 2000 | Minimum speech segment length |
| `min_silence_duration_ms` | 500 | 0 - 3000 | Minimum silence to split |
| `speech_pad_ms` | 100 | 0 - 500 | Padding around speech segments |

### VAD Output Format

```json
{
  "vad_enabled": true,
  "threshold": 0.5,
  "original_duration_ms": 300000,
  "speech_duration_ms": 180000,
  "silence_removed_ms": 120000,
  "segments": [
    {
      "index": 0,
      "start_ms": 5000,
      "end_ms": 45000,
      "duration_ms": 40000,
      "confidence": 0.89
    },
    {
      "index": 1,
      "start_ms": 47000,
      "end_ms": 120000,
      "duration_ms": 73000,
      "confidence": 0.92
    }
  ]
}
```

---

## Stage 3: Chunking Engine

### Chunking Strategy

```python
class ChunkingEngine:
    def __init__(self,
                 chunk_length_ms: int = 30000,  # 30 seconds
                 chunk_overlap_ms: int = 5000,  # 5 seconds
                 max_chunk_duration_ms: int = 30000):
        
        self.chunk_length_ms = chunk_length_ms
        self.chunk_overlap_ms = chunk_overlap_ms
        self.max_chunk_duration_ms = max_chunk_duration_ms
        
    def create_chunks(self, 
                      audio: AudioSegment,
                      vad_segments: List[SpeechSegment] = None) -> List[AudioChunk]:
        """
        Create overlapping chunks from audio or VAD segments.
        """
        chunks = []
        
        if vad_segments:
            # Use VAD segments as boundaries
            for segment in vad_segments:
                if segment.duration_ms <= self.max_chunk_duration_ms:
                    # Segment fits in one chunk
                    chunks.append(AudioChunk(
                        audio=segment.audio,
                        start_ms=segment.start_ms,
                        end_ms=segment.end_ms,
                        is_vad_segment=True
                    ))
                else:
                    # Split long VAD segment
                    segment_chunks = self._split_segment(segment)
                    chunks.extend(segment_chunks)
        else:
            # No VAD - use fixed-size chunks
            chunks = self._create_fixed_chunks(audio)
        
        return chunks
    
    def _split_segment(self, segment: SpeechSegment) -> List[AudioChunk]:
        """Split a long VAD segment into overlapping chunks."""
        chunks = []
        start_ms = segment.start_ms
        
        while start_ms < segment.end_ms:
            end_ms = min(start_ms + self.chunk_length_ms, segment.end_ms)
            
            chunk_audio = segment.audio[
                start_ms - segment.start_ms:
                end_ms - segment.start_ms
            ]
            
            chunks.append(AudioChunk(
                audio=chunk_audio,
                start_ms=start_ms,
                end_ms=end_ms,
                is_vad_segment=True
            ))
            
            # Move start with overlap
            start_ms += self.chunk_length_ms - self.chunk_overlap_ms
            
            # Don't create tiny final chunk
            if segment.end_ms - start_ms < 5000:  # 5 seconds minimum
                if chunks:
                    # Extend last chunk to cover remainder
                    last_chunk = chunks[-1]
                    last_chunk.end_ms = segment.end_ms
                    last_chunk.audio = segment.audio[
                        last_chunk.start_ms - segment.start_ms:
                    ]
                break
        
        return chunks
    
    def _create_fixed_chunks(self, audio: AudioSegment) -> List[AudioChunk]:
        """Create fixed-size overlapping chunks."""
        chunks = []
        start_ms = 0
        
        while start_ms < len(audio):
            end_ms = min(start_ms + self.chunk_length_ms, len(audio))
            
            chunks.append(AudioChunk(
                audio=audio[start_ms:end_ms],
                start_ms=start_ms,
                end_ms=end_ms,
                is_vad_segment=False
            ))
            
            start_ms += self.chunk_length_ms - self.chunk_overlap_ms
        
        return chunks
```

### Chunking Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `chunk_length_ms` | 30000 | 10000 - 60000 | Chunk duration in milliseconds |
| `chunk_overlap_ms` | 5000 | 0 - 10000 | Overlap between chunks |
| `max_chunk_duration_ms` | 30000 | 10000 - 60000 | Maximum chunk size |

### Chunk Output Format

```json
{
  "chunking_config": {
    "chunk_length_ms": 30000,
    "chunk_overlap_ms": 5000
  },
  "total_chunks": 12,
  "chunks": [
    {
      "index": 0,
      "start_ms": 0,
      "end_ms": 30000,
      "duration_ms": 30000,
      "is_vad_segment": true,
      "storage_path": "temp/job_xxx/chunks/chunk_0.wav"
    }
  ]
}
```

---

## Stage 4: ASR Engine (faster-whisper)

### Model Configuration

```python
from faster_whisper import WhisperModel

class ASREngine:
    def __init__(self, 
                 model_size: str = "base",
                 compute_type: str = "float16",
                 device: str = "cuda"):
        
        self.model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            cpu_threads=4 if device == "cpu" else 0,
            num_workers=1
        )
        self.model_size = model_size
        
    def transcribe(self, 
                   audio_path: str,
                   language: str = None,
                   beam_size: int = 5,
                   best_of: int = 5,
                   patience: float = 1.0,
                   temperature: float = 0.0,
                   compression_ratio_threshold: float = 2.4,
                   log_prob_threshold: float = -1.0,
                   no_speech_threshold: float = 0.6,
                   condition_on_previous_text: bool = True,
                   initial_prompt: str = None,
                   word_timestamps: bool = False) -> TranscriptionResult:
        
        segments, info = self.model.transcribe(
            audio_path,
            language=language,
            beam_size=beam_size,
            best_of=best_of,
            patience=patience,
            temperature=temperature,
            compression_ratio_threshold=compression_ratio_threshold,
            log_prob_threshold=log_prob_threshold,
            no_speech_threshold=no_speech_threshold,
            condition_on_previous_text=condition_on_previous_text,
            initial_prompt=initial_prompt,
            word_timestamps=word_timestamps,
            vad_filter=False,  # We already did VAD
            vad_parameters=None
        )
        
        # Convert generator to list
        segment_list = list(segments)
        
        return TranscriptionResult(
            language=info.language,
            language_probability=info.language_probability,
            duration=info.duration,
            segments=[self._convert_segment(s) for s in segment_list],
            text=" ".join([s.text for s in segment_list])
        )
    
    def _convert_segment(self, segment) -> TranscriptionSegment:
        return TranscriptionSegment(
            id=segment.id,
            start=segment.start,
            end=segment.end,
            text=segment.text.strip(),
            words=[self._convert_word(w) for w in (segment.words or [])],
            confidence=segment.avg_logprob,
            no_speech_prob=segment.no_speech_prob
        )
    
    def _convert_word(self, word) -> WordTimestamp:
        return WordTimestamp(
            word=word.word.strip(),
            start=word.start,
            end=word.end,
            confidence=word.probability
        )
```

### Transcription Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `model` | base | tiny/base/small/medium/large-v3 | Model size |
| `compute_type` | float16 | float16/int8/float32 | Precision |
| `beam_size` | 5 | 1 - 10 | Beam search width |
| `best_of` | 5 | 1 - 10 | Number of candidates |
| `patience` | 1.0 | 0.5 - 2.0 | Beam search patience |
| `temperature` | 0.0 | 0.0 - 1.0 | Sampling temperature |
| `condition_on_previous_text` | true | bool | Context carryover |
| `word_timestamps` | false | bool | Word-level timing |

### Transcription Output Format

```json
{
  "language": "en",
  "language_probability": 0.98,
  "duration": 30.0,
  "text": "The quick brown fox jumps over the lazy dog.",
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 3.2,
      "text": "The quick brown fox jumps over the lazy dog.",
      "words": [
        {"word": "The", "start": 0.0, "end": 0.2, "confidence": 0.97},
        {"word": "quick", "start": 0.2, "end": 0.5, "confidence": 0.93},
        {"word": "brown", "start": 0.5, "end": 0.8, "confidence": 0.95},
        {"word": "fox", "start": 0.8, "end": 1.1, "confidence": 0.96},
        {"word": "jumps", "start": 1.1, "end": 1.5, "confidence": 0.94},
        {"word": "over", "start": 1.5, "end": 1.8, "confidence": 0.92},
        {"word": "the", "start": 1.8, "end": 2.0, "confidence": 0.98},
        {"word": "lazy", "start": 2.0, "end": 2.4, "confidence": 0.91},
        {"word": "dog", "start": 2.4, "end": 2.8, "confidence": 0.95}
      ],
      "confidence": 0.94,
      "no_speech_prob": 0.02
    }
  ]
}
```

---

## Stage 5: Optional Modules

### Diarization (Speaker Separation)

```python
class DiarizationModule:
    def __init__(self, model_name: str = "pyannote/speaker-diarization"):
        from pyannote.audio import Pipeline
        
        self.pipeline = Pipeline.from_pretrained(model_name)
        
    def process(self, 
                audio_path: str,
                num_speakers: int = None,
                min_speakers: int = None,
                max_speakers: int = None) -> List[SpeakerSegment]:
        
        diarization = self.pipeline(
            audio_path,
            num_speakers=num_speakers,
            min_speakers=min_speakers,
            max_speakers=max_speakers
        )
        
        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append(SpeakerSegment(
                start=turn.start,
                end=turn.end,
                speaker=speaker,
                confidence=1.0  # pyannote doesn't provide confidence
            ))
        
        return segments
    
    def merge_with_transcript(self,
                              transcript: TranscriptionResult,
                              speaker_segments: List[SpeakerSegment]) -> TranscriptionResult:
        """Assign speaker labels to transcript segments."""
        for seg in transcript.segments:
            # Find overlapping speaker segments
            overlapping = [
                s for s in speaker_segments
                if s.start < seg.end and s.end > seg.start
            ]
            
            if overlapping:
                # Assign speaker with most overlap
                best_speaker = max(overlapping, 
                    key=lambda s: min(s.end, seg.end) - max(s.start, seg.start))
                seg.speaker = best_speaker.speaker
            else:
                seg.speaker = "UNKNOWN"
        
        return transcript
```

### Word Alignment (Fine-grained Timestamps)

```python
class WordAlignmentModule:
    def __init__(self):
        # Uses whisper-timestamped for better word alignment
        import whisper_timestamped
        self.whisper_timestamped = whisper_timestamped
        
    def process(self,
                audio_path: str,
                transcript: TranscriptionResult,
                model_name: str = "base") -> TranscriptionResult:
        
        # Re-process with timestamped model for better alignment
        aligned = self.whisper_timestamped.transcribe(
            model_name,
            audio_path,
            language=transcript.language,
            verbose=False
        )
        
        # Merge aligned words with existing transcript
        for seg_idx, segment in enumerate(transcript.segments):
            if seg_idx < len(aligned["segments"]):
                aligned_words = aligned["segments"][seg_idx].get("words", [])
                segment.words = [
                    WordTimestamp(
                        word=w["text"].strip(),
                        start=w["start"],
                        end=w["end"],
                        confidence=w.get("confidence", 0.0)
                    )
                    for w in aligned_words
                ]
        
        return transcript
```

---

## Stage 6: Post-Processing

### Segment Merging

```python
class PostProcessor:
    def __init__(self,
                 merge_threshold_ms: int = 500,  # Merge segments < 500ms apart
                 max_segment_duration: int = 30000):
        
        self.merge_threshold_ms = merge_threshold_ms
        self.max_segment_duration = max_segment_duration
        
    def merge_segments(self, 
                       segments: List[TranscriptionSegment],
                       chunk_offsets: List[float] = None) -> List[TranscriptionSegment]:
        """
        Merge segments from multiple chunks, adjusting timestamps.
        """
        if not segments:
            return []
        
        # Adjust timestamps for chunk offsets
        if chunk_offsets:
            for i, seg in enumerate(segments):
                chunk_start = chunk_offsets[i]
                seg.start += chunk_start
                seg.end += chunk_start
                for word in seg.words:
                    word.start += chunk_start
                    word.end += chunk_start
        
        # Sort by start time
        segments = sorted(segments, key=lambda s: s.start)
        
        # Merge close segments with same speaker
        merged = []
        current = segments[0]
        
        for next_seg in segments[1:]:
            gap_ms = (next_seg.start - current.end) * 1000
            same_speaker = current.speaker == next_seg.speaker
            within_duration = (next_seg.end - current.start) < self.max_segment_duration
            
            if gap_ms < self.merge_threshold_ms and same_speaker and within_duration:
                # Merge segments
                current.end = next_seg.end
                current.text += " " + next_seg.text
                current.words.extend(next_seg.words)
                current.confidence = (current.confidence + next_seg.confidence) / 2
            else:
                merged.append(current)
                current = next_seg
        
        merged.append(current)
        
        # Renumber segments
        for i, seg in enumerate(merged):
            seg.id = i
        
        return merged
    
    def format_output(self,
                      transcript: TranscriptionResult,
                      format_type: str) -> str:
        """Format transcript to SRT, VTT, TXT, or JSON."""
        
        if format_type == "json":
            return json.dumps({
                "language": transcript.language,
                "language_probability": transcript.language_probability,
                "duration": transcript.duration,
                "text": transcript.text,
                "segments": [
                    {
                        "id": s.id,
                        "start": s.start,
                        "end": s.end,
                        "text": s.text,
                        "speaker": s.speaker,
                        "confidence": s.confidence,
                        "words": [
                            {
                                "word": w.word,
                                "start": w.start,
                                "end": w.end,
                                "confidence": w.confidence
                            } for w in s.words
                        ] if s.words else None
                    }
                    for s in transcript.segments
                ]
            }, indent=2)
        
        elif format_type == "srt":
            return self._to_srt(transcript.segments)
        
        elif format_type == "vtt":
            return self._to_vtt(transcript.segments)
        
        elif format_type == "txt":
            return transcript.text
        
        else:
            raise ValueError(f"Unknown format: {format_type}")
    
    def _to_srt(self, segments: List[TranscriptionSegment]) -> str:
        lines = []
        for seg in segments:
            start = self._format_timestamp(seg.start, "srt")
            end = self._format_timestamp(seg.end, "srt")
            speaker = f"[{seg.speaker}] " if seg.speaker else ""
            lines.append(f"{seg.id + 1}\n{start} --> {end}\n{speaker}{seg.text}\n")
        return "\n".join(lines)
    
    def _to_vtt(self, segments: List[TranscriptionSegment]) -> str:
        lines = ["WEBVTT\n"]
        for seg in segments:
            start = self._format_timestamp(seg.start, "vtt")
            end = self._format_timestamp(seg.end, "vtt")
            speaker = f"<v {seg.speaker}>" if seg.speaker else ""
            lines.append(f"{start} --> {end}\n{speaker}{seg.text}\n")
        return "\n".join(lines)
    
    def _format_timestamp(self, seconds: float, format_type: str) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        
        if format_type == "srt":
            return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
        else:  # vtt
            return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
```

---

## Complete Pipeline Execution

```python
class TranscriptionPipeline:
    def __init__(self, config: PipelineConfig):
        self.vad = VADProcessor(threshold=config.vad_threshold)
        self.chunker = ChunkingEngine(
            chunk_length_ms=config.chunk_length_ms,
            chunk_overlap_ms=config.chunk_overlap_ms
        )
        self.asr = ASREngine(
            model_size=config.model,
            compute_type=config.compute_type
        )
        self.diarization = DiarizationModule() if config.diarization_enabled else None
        self.alignment = WordAlignmentModule() if config.word_timestamps else None
        self.postprocessor = PostProcessor()
        
    async def process(self, 
                      job_id: str,
                      audio_path: str,
                      progress_callback: Callable = None) -> TranscriptionResult:
        
        # 1. Load and validate audio
        audio = AudioSegment.from_file(audio_path)
        
        # 2. VAD (optional)
        vad_segments = None
        if self.vad:
            await self._report_progress(job_id, "vad", 10, progress_callback)
            vad_segments = self.vad.process(audio)
        
        # 3. Chunking
        await self._report_progress(job_id, "chunking", 20, progress_callback)
        chunks = self.chunker.create_chunks(audio, vad_segments)
        
        # 4. Transcribe each chunk
        all_segments = []
        chunk_offsets = []
        
        for i, chunk in enumerate(chunks):
            progress = 30 + int((i / len(chunks)) * 50)
            await self._report_progress(
                job_id, "transcribing", progress, progress_callback,
                chunks_processed=i, chunks_total=len(chunks)
            )
            
            # Save chunk to temp file
            chunk_path = f"/tmp/{job_id}_chunk_{i}.wav"
            chunk.audio.export(chunk_path, format="wav")
            
            # Transcribe
            result = self.asr.transcribe(
                chunk_path,
                language=config.language if config.language != "auto" else None,
                word_timestamps=config.word_timestamps
            )
            
            all_segments.extend(result.segments)
            chunk_offsets.append(chunk.start_ms / 1000)
            
            # Cleanup
            os.remove(chunk_path)
        
        # 5. Diarization (optional)
        if self.diarization:
            await self._report_progress(job_id, "diarization", 85, progress_callback)
            speaker_segments = self.diarization.process(audio_path)
            all_segments = self.diarization.merge_with_transcript(
                TranscriptionResult(segments=all_segments),
                speaker_segments
            ).segments
        
        # 6. Word alignment (optional)
        if self.alignment:
            await self._report_progress(job_id, "alignment", 90, progress_callback)
            # Re-process for better alignment
            pass
        
        # 7. Post-process
        await self._report_progress(job_id, "formatting", 95, progress_callback)
        merged_segments = self.postprocessor.merge_segments(
            all_segments, chunk_offsets
        )
        
        # Build final result
        result = TranscriptionResult(
            language=all_segments[0].language if all_segments else "unknown",
            duration=len(audio) / 1000,
            text=" ".join([s.text for s in merged_segments]),
            segments=merged_segments
        )
        
        await self._report_progress(job_id, "completed", 100, progress_callback)
        
        return result
    
    async def _report_progress(self, job_id: str, step: str, 
                               percent: int, callback: Callable = None,
                               **kwargs):
        if callback:
            await callback(job_id, {
                "step": step,
                "percent": percent,
                **kwargs
            })
```

---

## Error Handling

### Error Taxonomy

| Error Code | Stage | Retryable | Description |
|------------|-------|-----------|-------------|
| `VALIDATION_ERROR` | Input | No | Invalid file format or size |
| `AUDIO_DECODE_ERROR` | Input | No | Cannot decode audio file |
| `VAD_ERROR` | VAD | Yes | VAD processing failed |
| `CHUNKING_ERROR` | Chunking | Yes | Failed to create chunks |
| `TRANSCRIPTION_ERROR` | ASR | Yes | Model inference failed |
| `GPU_OOM_ERROR` | ASR | Yes | GPU out of memory |
| `DIARIZATION_ERROR` | Diarization | Yes | Speaker separation failed |
| `ALIGNMENT_ERROR` | Alignment | Yes | Word alignment failed |
| `STORAGE_ERROR` | Output | Yes | Failed to save results |
| `TIMEOUT_ERROR` | Any | Yes | Processing timeout |

### Retry Strategy

```python
RETRY_CONFIG = {
    "max_retries": 3,
    "backoff_factor": 2,
    "initial_delay": 1,  # seconds
    "max_delay": 60,  # seconds
    "retryable_errors": [
        "VAD_ERROR",
        "CHUNKING_ERROR", 
        "TRANSCRIPTION_ERROR",
        "GPU_OOM_ERROR",
        "DIARIZATION_ERROR",
        "ALIGNMENT_ERROR",
        "STORAGE_ERROR",
        "TIMEOUT_ERROR"
    ]
}

def calculate_retry_delay(attempt: int) -> float:
    delay = RETRY_CONFIG["initial_delay"] * (RETRY_CONFIG["backoff_factor"] ** attempt)
    return min(delay, RETRY_CONFIG["max_delay"])
```
