# Feature: Kiến thức nền — edit video / TTS / sub (long-tieng)

## Mục đích

Lộ trình **đọc hiểu** để tự điều chỉnh dự án lồng tiếng + edit đủ đăng YouTube. Không phải syllabus CS đầy đủ. Đọc theo thứ tự bước sản phẩm trong `long-tieng.md`.

## Surfaces

- Sản phẩm: `docs/features/long-tieng.md`
- Codex ngoài: `docs/features/codex.md`
- Demo code: `long-tieng/app.py`

## Cách dùng file này

1. Đọc **Khái niệm phải nắm** của bước đang làm.
2. Mở **1–2 link** (không đọc cả sách).
3. Quay lại chỉnh sản phẩm / hỏi agent theo đúng thuật ngữ.

### Không học gì (bây giờ)

| Bỏ qua | Vì sao |
|--------|--------|
| Tối ưu phần mềm (Big-O, cache, multithread, GPU kernel…) | Chưa có sản phẩm đăng được; tối ưu sớm = nhiễu |
| Kiến trúc microservices / Kafka / Redis | Stack đã chốt mỏng (`ARCHITECTURE.md`) |
| Train model TTS từ đầu | Dùng model có sẵn (VieNeu); chỉ hiểu clone vs fine-tune |
| Thuật toán encode H.264 chi tiết | Biết “re-encode vs copy” là đủ |

Học **đường ống sản phẩm** (tiếng → video → chữ → cắt), không học “làm kỹ sư hệ thống”.

### Để không bị “agent code mà mình không hiểu”

1. Mỗi lần chỉ **một bước** lộ trình (vd chỉ mux), không xin “làm hết studio”.
2. Trước khi code: đọc mục kiến thức tương ứng **15–30 phút**.
3. Sau khi có diff: bắt agent giải thích **luồng file + lệnh**, không giải thích tối ưu.
4. Bạn tự chạy 1 lần tay (ffmpeg / Gradio) → mới tin.
5. Sự thật nằm ở `long-tieng.md` + file này — chat không thay doc.

---

## Bản đồ kiến thức ↔ pipeline

```text
Âm thanh / TTS     →  Video container / ffmpeg  →  Thời gian & sync
       ↓                        ↓                        ↓
   STT / chữ              Sub A (SRT/ASS)           Studio B (caption)
       ↓                        ↓                        ↓
   Dịch / NLP              Cắt ghép                 Nghệ thuật chữ
```

| Bước sản phẩm | Khối kiến thức | Độ sâu đủ dùng |
|---------------|----------------|----------------|
| 1 TTS | Sóng âm, sample rate, clone vs train | Hiểu vì sao 8s / vì sao “đớ” |
| 2 Mux | Container mp4, stream A/V, ffmpeg | Ghép tiếng không lệch |
| 3 Sub A | Timeline, SRT/ASS, burn | Chữ đúng chỗ đúng lúc |
| 4 STT + dịch | ASR, timestamp, dịch máy | Câu khớp miệng |
| 5 Cắt | GOP, keyframe, trim | Cắt không vỡ hình |
| 6 Studio B | Word timing, motion, typography | Hiệu ứng “nói tới đâu chữ tới đó” |

---

## 1 — Âm thanh & TTS (đang làm)

**Khái niệm**

| Thuật ngữ | Nghĩa ngắn | Liên quan app |
|-----------|------------|---------------|
| Sample rate | Số mẫu/giây (16k / 44.1k / 48k) | VieNeu ra 48 kHz; lệch SR → méo |
| Mono / stereo | 1 hay 2 kênh | Clone nên mono |
| Waveform / RMS | Biên độ âm | Chọn “đoạn rõ nhất” 8s |
| Zero-shot clone | Mẫu ngắn → tembre, **không** train lại | Gửi giọng hoài ≠ học thêm |
| Speaker embedding | Vector “ai đang nói” | `speaker_emb` |
| Codec / ref codes | Mã âm thanh mẫu trong prompt | File dài → đớ; VieNeu ~8s |
| Phoneme | Đơn vị phát âm | Text → phoneme → audio |
| Prosody | Nhịp, cao độ, nhấn | Dấu câu + mẫu nói có nhịp |

**Đọc**

- [Digital Audio Basics (MDN)](https://developer.mozilla.org/en-US/docs/Web/Media/Formats/Audio_concepts) — sample rate, bit depth
- [VieNeu-TTS README](https://github.com/pnnbao97/VieNeu-TTS) — clone ≤8s, preset voices
- (Tuỳ) “What is voice cloning” — phân biệt clone vs fine-tune (bất kỳ bài phổ thông rõ ràng)

**Toán vừa đủ:** không cần Fourier sâu. Biết: tín hiệu rời rạc theo thời gian; năng lượng ~ trung bình bình phương biên độ (RMS) — đúng chỗ app chọn cửa sổ 8s.

**Nghệ thuật:** giọng đọc sạch, tốc độ nói bình thường, tránh hát/ASMR — đã ghi trong `long-tieng.md`. Phong cách theo thể loại (truyện ma chậm + vang, tin tức rõ) = **hậu kỳ** `atempo` / `aecho` / EQ, không phải model “diễn”.

---

## 2 — Video + ghép tiếng (ffmpeg)

**Khái niệm**

| Thuật ngữ | Nghĩa | Việc cần làm |
|-----------|-------|--------------|
| Container (mp4) | Hộp chứa video + audio + phụ đề | Xuất 1 file đăng |
| Stream | Luồng riêng (H.264, AAC…) | Mux = ghép stream |
| Mux / demux | Ghép / tách | `ffmpeg -i video -i voice …` |
| PTS / DTS | Mốc thời gian trong file | Lệch PTS = tiếng trễ |
| atempo / rubberband | Đổi tốc độ audio giữ pitch (gần) | Câu TTS dài hơn cảnh |
| Re-encode vs copy | Encode lại vs copy stream | Trim “copy” nhanh nhưng cứng GOP |

**Đọc**

- [ffmpeg Wiki — Understanding](https://trac.ffmpeg.org/wiki) mục Encoding / Concat (chọn trang ngắn)
- [ffmpeg muxing](https://ffmpeg.org/ffmpeg.html#Stream-selection) — ý “map stream”
- Thực hành: 5 lệnh — tách tiếng, thay tiếng, trim, nối 2 đoạn, burn sub

**Toán vừa đủ:** thời gian tuyến tính `t`; tỷ lệ `độ_dài_TTS / độ_dài_cảnh` → hệ số atempo.

---

## 3 — Sub lớp A (SRT / ASS)

**Khái niệm**

| Thuật ngữ | Nghĩa |
|-----------|-------|
| Timecode | `HH:MM:SS,mmm` |
| SRT | Sub đơn giản: thời gian + text |
| ASS/SSA | Sub có style, vị trí, karaoke thô |
| Burn-in | Vẽ chữ vào pixel video (không tắt được) |
| Soft sub | Track phụ đề tách (bật/tắt) |
| Safe area | Vùng chữ không sát mép / không đè mặt |

**Đọc**

- [SRT format](https://en.wikipedia.org/wiki/SubRip)
- [ASS Spec (tóm tắt)](https://github.com/libass/libass/wiki/ASS-File-Format-Guide) — chỉ phần Style + Dialogue
- YouTube: “caption safe margins” / mobile 9:16 — chữ giữa–dưới

**Nghệ thuật:** tối đa ~2 dòng; contrast; font dày Shorts; tránh chữ nhỏ full câu.

---

## 4 — STT, timestamp, dịch

**Khái niệm**

| Thuật ngữ | Nghĩa |
|-----------|-------|
| ASR / STT | Giọng → chữ |
| Word / segment timestamp | Mốc từng từ hoặc từng câu |
| WER | Tỷ lệ lỗi chữ (đánh giá, không bắt buộc code) |
| Forced alignment | Ghép sẵn chữ với audio theo thời gian |
| MT (machine translation) | Dịch máy; giữ số câu ≈ SRT gốc |

**Đọc**

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — segment timestamps
- Whisper paper / blog phổ thông: “chunks + timestamps” (không cần đọc full paper)
- Dịch: giữ **cùng số cue** SRT; Codex ngoài = biên tập viên, không phải engine trong app (`codex.md`)

---

## 5 — Cắt ghép

**Khái niệm**

| Thuật ngữ | Nghĩa |
|-----------|-------|
| Frame / fps | Khung hình / giây (24, 30, 60) |
| Keyframe (I-frame) / GOP | Điểm cắt “sạch”; cắt giữa GOP dễ glitch nếu `-c copy` |
| Edit decision (EDL) | Danh sách đoạn giữ/bỏ |
| Concat demuxer | Nối file cùng codec |

**Đọc**

- ffmpeg: “seeking”, “concat demuxer”
- Hiểu khi nào cần re-encode (`-c:v libx264`) vs copy

---

## 6 — Studio caption (lớp B) — đọc sau

**Khái niệm**

| Thuật ngữ | Nghĩa |
|-----------|-------|
| Kinetic typography | Chữ chuyển động theo nghĩa/nhịp |
| Word-level highlight | Từ đang nói được nhấn (màu/scale) |
| Karaoke / \k tags (ASS) | Hiệu ứng theo thời gian trong ASS |
| Motion (ease) | Ease-in/out — cảm giác “nẩy” |
| Remotion / Canvas | Render chữ bằng code/frame |

**Đọc (khi tới bước 6)**

- [The Basics of Kinetic Typography](https://www.smashingmagazine.com/2012/02/the-basics-of-kinetic-typography/) (ý tưởng, không bắt buộc tool)
- CapCut / Shorts: xem 10 video cùng ngách → ghi **1** kiểu chữ mình sẽ copy (không 20 template)
- Kỹ thuật: ASS karaoke **hoặc** Remotion — chọn **một** stack

**Nghệ thuật:** một font, một màu nhấn, một hiệu ứng; nói chậm hơn chữ bay loạn.

**Toán vừa đủ:** nội suy (lerp) scale/opacity theo `t` trong `[t0, t1]`; easing đơn giản `(1-cos(πt))/2`.

---

## Toán — chỉ cần mức này

| Chủ đề | Dùng để | Không cần |
|--------|---------|-----------|
| Tỷ lệ / nội suy tuyến tính | atempo, fade, scale chữ | Giải tích nặng |
| RMS / max | Chọn đoạn audio rõ | DSP đầy đủ |
| Đếm frame = `t * fps` | Sync sub | Lý thuyết tín hiệu |
| Vector 192-d (embedding) | Biết “là fingerprint giọng” | Tự train embedding |

---

## Nghệ thuật / sản phẩm (song song kỹ thuật)

1. **Một thể loại clip** — cùng layout chữ, cùng chỗ sub (`saas-ngach.md` #4).
2. Hook 3s đầu: chữ lớn + một ý.
3. Nghe lại: tiếng rõ hơn effect.
4. Consent giọng — không rip YouTube / app trả phí để “free”.

---

## Thứ tự đọc tuần này (thực dụng)

| Ngày | Đọc | Xong khi… |
|------|-----|-----------|
| 1–2 | Mục 1 (audio + VieNeu README) | Giải thích được vì sao 8s, clone ≠ train |
| 3–4 | Mục 2 (ffmpeg mux) | Tự ghép 1 video + 1 wav ra mp4 bằng tay |
| 5 | Mục 3 (SRT + safe area) | Viết 1 file SRT 5 câu + burn thử |
| Sau | Mục 4–5 | Khi làm STT / cắt trong app |
| Muộn | Mục 6 | Khi lớp A đã đăng được clip |

## Phụ thuộc

`docs/features/long-tieng.md` (lộ trình sản phẩm). Không thay bài test.

## Code chính

- Không có code riêng — tài liệu đọc.
- Thực hành lệnh gắn `long-tieng/out/` + ffmpeg trên máy.

## Changelog

- 2026-08-27: phong cách đọc (truyện ma vang, tin tức rõ) = hậu kỳ ffmpeg, không phải TTS diễn.
- 2026-08-16: không học tối ưu sớm; cách làm việc để hiểu code (một bước / giải thích luồng / tự chạy).
- 2026-08-16: lộ trình kiến thức kỹ thuật / toán vừa đủ / nghệ thuật theo 6 bước pipeline.
