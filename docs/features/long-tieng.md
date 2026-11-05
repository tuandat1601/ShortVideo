# Feature: Lồng tiếng / sub

## Mục đích

Sub + lồng tiếng **một thể loại clip**, rồi nới thành **máy edit đủ đăng YouTube** (thay CapCut ở vài việc quan trọng — không clone CapCut đầy đủ).

Demo đang có: TTS / clone giọng local (VieNeu). **Wizard cửa 1–7 (lát A–E)** chạy được: nhập → STT → dịch/khóa → TTS tốc độ/volume → vị trí sub → mp4 có chữ + giọng.

**Thành công = xuất được mp4 đăng được**, không phải đủ timeline CapCut.

## Wizard 7 cửa (chốt 2026-08-18)

**Luồng user bắt buộc đúng thứ tự này** — không chạy một nút “làm hết”. Mỗi cửa có file ra; cửa sau khóa nếu cửa trước chưa xong / user chưa bấm tiếp.

```text
1. Nhập video
2. Lấy sub (STT)          ← dừng, hiện SRT gốc để sửa
3. Dịch                   ← chỉ sau khi sub gốc OK
4. Đọc / sửa bản dịch     ← người duyệt, chưa TTS
5. Nhét giọng             ← clone giọng mình; chỉnh tốc độ + âm lượng
6. Vị trí sub             ← kéo chữ trên khung preview; preset / nền / màu; xuất mp4
7. Xuất mp4               ← video + sub burn + giọng mới
```

Giữ tab TTS cũ (đọc một đoạn text) bên cạnh. Wizard là tab **Video**.

### Cửa 1 — Nhập video

- UI: `gr.Video` / upload mp4, mov, mkv, webm. Local only, không URL lần đầu.
- Job: `long-tieng/jobs/<id>/` — copy `source.mp4`.
- ffmpeg: `ffprobe` (độ dài, fps, WxH) + tách `audio_orig.wav` (mono 16 kHz cho STT; 48 kHz giữ bản mux).
- Gate: có file + có tiếng. Video câm → báo, không sang cửa 2.
- Chưa: tải YouTube/TikTok.

### Cửa 2 — Lấy sub (STT)

- Engine: **faster-whisper local** (model `small` mặc định; `base` nếu máy yếu). ChatGPT free không nghe file.
- Ra: `orig.srt` — mỗi cue = một đoạn Whisper (giữ timestamp).
- UI: bảng/textarea SRT (bắt đầu–kết + chữ). Sửa tay được. Nút **Tách lại** nếu chọn model khác.
- Gate: **Dùng bản sub này** → `orig.srt` + `target.srt` (bản gốc, nếu chưa có `final.srt`). Cùng ngôn ngữ: sang **4 Giọng** được. Dịch không chạy ngầm lúc STT.

### Cửa 3 — Dịch

- Chỉ dịch **text từng cue**, giữ **cùng số cue + cùng timestamp**. Không dịch lại thời gian. Cloud AI **chỉ cửa này** (STT Whisper local, TTS VieNeu local).
- Engine dịch (tab **Cài đặt**, BYOK):
  1. Gemini hoặc OpenAI — dán key + chọn model, Lưu. Có thể lưu **cả hai** key (đổi radio, dán key, Lưu từng máy). File `long-tieng/settings.json` (gitignore).
  2. Ollama local — tùy, không bắt buộc.
  3. **Nhanh:** copy `orig.srt` (ô trái) → Gemini/ChatGPT chat → dán ô phải hoặc gửi file `.srt` → **Dùng bản dán** (ghi luôn `final.srt`). Lệch số câu / lời dẫn chat: bỏ preamble, ghép mốc giờ gốc, thiếu câu thì giữ orig — không kẹt “khóa cửa 3”. Nút **Khóa bản đọc** nếu sửa thêm. **Dịch (API)** cũng khóa sau khi dịch. Sang **4 Giọng**: ô dán → `target.srt` → `orig.srt` đã khóa cửa 2.
- Máy đang chọn chạy trước. Lô lỗi / 429 → OpenAI/Gemini/Ollama nếu có key (không thử thêm 2 model Gemini khi đã có OpenAI — tránh chờ). Dòng trạng thái: `Gemini/x → OpenAI/y`.
- Prompt: gộp **80 câu/lô** (tối đa 100 một request; >100 thì cắt 80). Gửi SRT (số + timestamp + thoại). Chỉ dẫn: *Chỉ dịch nội dung thoại, giữ nguyên timestamp và số thứ tự, không giải thích thêm.* App **dán lại mốc giờ gốc** — AI không được đổi time. Sai số câu → cắt 50 rồi gọi lại. OpenAI nhiều lô thì song song 3.
- TTS/clone giọng **không** dùng cloud key — vẫn VieNeu local.
- Ra: `vi.srt` (hoặc `target.srt`).
- Gate: có `final.srt` hoặc đã khóa `orig.srt`. Chưa TTS.

### Cửa 4 — Đọc / sửa bản dịch

- UI: hai cột (gốc | dịch) hoặc một editor SRT dịch + player video gốc (nghe đối chiếu).
- User sửa chữ, xuống dòng. Timestamp mặc định giữ; cho sửa nếu lệch miệng nặng.
- Nút **Nghe thử 1 câu** (TTS 1 cue) — tùy, không bắt buộc trước cửa 5.
- Gate: **Khóa bản đọc** / **Dùng bản dán** / sang Giọng → `final.srt`. Thiếu ô dán thì đọc `orig.srt` (đã khóa cửa 2). Tách tiếng lại **không** tạo job mới nếu thanh Job đã có id.

### Cửa 5 — Nhét giọng (phong cách + tốc độ + âm lượng)

- Giọng: dropdown sẵn VieNeu + file `voice/` (code TTS hiện có). Checkbox consent như tab TTS.
- **Nguồn mẫu giọng (ngoài app):** [YupVox Text to Speech](https://yupvox.com/text-to-speech) — chọn giọng trên web, xuất mp3 (CDN `cdn.yupvox.com/tts/…`), bỏ vào `long-tieng/voice/`, **Làm mới giọng**. App **không** gọi API YupVox; vẫn VieNeu local clone từ file. Enroll ~8s đoạn rõ nhất. File ví dụ: `voice/yupvox-1203-6226.mp3`.
- TTS **từng cue** của `final.srt` (tự khóa từ dán / orig nếu thiếu) → `cues/0001.wav` … (bắt buộc để canh mốc SRT; 149 câu = 149 lần VieNeu, không gộp một prompt). Ô trạng thái hiện `Đọc k/n`. Đổi slider tốc độ/volume **hoặc phong cách** không TTS lại nếu cùng chữ+giọng (chỉ ffmpeg fit + FX).
- **Phong cách đọc** (dropdown, mặc định Bình thường): chọn preset rồi **Nghe thử**. Chọn xong app gán tốc độ/âm lượng; vẫn chỉnh slider được. VieNeu không “diễn” theo thể loại — style = hậu kỳ ffmpeg (tốc độ + EQ + vang).
  - **Truyện ma:** chậm (~0.88), rõ (highpass + treble), hơi vang ám ảnh (`aecho` ngắn + đuôi ~0.28s). Không thì thầm.
  - **Tin tức:** hơi sáng, rõ.
  - **Kể chuyện:** chậm ấm.
  - **Năng lượng:** nhanh, bật.
- **Tốc độ đọc** (slider 0.80–1.25, mặc định 1.00): `ffmpeg atempo` trên từng cue (giữ pitch). Ngoài 0.5–2.0 thì ghép hai `atempo`.
- **Âm lượng** (slider 0.5–2.0 = −6 dB … +6 dB): `volume=` lúc mix. Style FX (vang) **sau** khi canh mốc — không đẩy atempo thêm vì đuôi echo.
- Sync: TTS dài hơn mốc SRT (câu 0.6–0.9s như “hơn 8 năm!”) → tăng tốc tối đa ~1.35, **không cắt đuôi** (cắt = nuốt chữ). Còn dài thì tràn ~0.3s sang câu sau. Câu ngắn hơn mốc: wav ngắn, chỗ trống = silence.
- Nối cue theo timeline → `voice_new.wav`. Chỗ không có sub = silence (MVP không tách nhạc nền).
- Mix: thay audio gốc. Sau MVP: slider “nhạc gốc còn lại” (volume orig thấp), chưa Demucs.
- **Nghe thử**: nút phát 1 câu ngắn (mẫu sẵn, hoặc câu đầu `final.srt` sau khi khóa) + đúng phong cách/tốc độ/âm lượng. TTS raw cache — đổi slider hoặc style bấm lại chỉ chạy ffmpeg, không đọc cả clip.
- UI: nghe thử rồi mới **Đọc + ghép giọng** → `voice_new.wav`.
- Gate: có `voice_new.wav` + user nghe ổn.

### Cửa 6 — Vị trí sub trên khung

Lớp **A** (burn cố định). Kéo chữ **trên khung preview** (không slider %). Preset Dưới/Giữa/Trên chỉ nhảy nhanh.

- Bấm **5 Xuất** (hoặc **Xem khung**) → 1 frame + **ô chữ kéo được** (viền xanh). Kéo ô để đặt vị trí; kéo **tay cầm hai bên** đổi độ dài / xuống dòng. Không kéo trên video Mp4 cuối (đã đốt sẵn). Kéo chạy trong `js_on_load` của ô HTML (Gradio 6) — viền xanh chỉ là CSS, không phải script kéo.
- **Style chữ (Pillow burn):** dropdown **Font** (font hệ thống Mac còn file: Arial Bold / Black / Impact / DIN Condensed…), ColorPicker **Màu chữ** (mặc định trắng `#FFFFFF`), slider **Cỡ chữ** 20–120 px (mặc định 48). Đổi → preview HTML cập nhật ngay; Xuất dùng cùng tham số lúc vẽ PNG.
- Nền: checkbox **Có nền chữ** + ColorPicker + thanh **Đậm nền** 40–100% (mặc định 95% để che chữ gốc). Color picker Gradio không có alpha — độ phủ nằm ở slider.
- Homebrew `ffmpeg` **không** có libass/`drawtext` → không `ass=`. Vẽ PNG trong suốt (Pillow) rồi `overlay`.
- Ra: `subs/*.png` + file đánh dấu `style.ass` (ghi font/size/màu).
- Gate: đã kéo/xem ổn rồi **Xuất**.

### Cửa 7 — Xuất mp4

```text
ffmpeg -i source.mp4 -i voice_new.wav -f concat -i subs/concat.txt
  overlay 1 lần (luồng chữ = PNG nối theo mốc SRT)
  encode h264_videotoolbox (Mac) / libx264 veryfast nếu GPU lỗi
  out/<id>_final.mp4
```

Không mở từng câu một input `-loop 1 -i cue.png` rồi chồng N lớp `overlay` — video 4 phút ~100–200 câu sẽ rất chậm.

- Video copy độ phân giải gốc; re-encode vì burn sub (không `-c:v copy`).
- Soft sub (track tắt/bật) = tùy chọn phụ; mặc định **burn-in** (đăng Shorts/YT chắc chữ).
- File ra: `long-tieng/out/<id>_final.mp4` + hiện `gr.Video`.
- Thành công cửa 7 = clip đăng được. Cắt/nối và studio lớp B **sau**.

### File trên đĩa (một job)

```text
long-tieng/jobs/<id>/
  source.mp4
  audio_orig.wav
  orig.srt          # cửa 2
  target.srt        # cửa 3
  final.srt         # cửa 4 (sau sửa)
  cues/*.wav        # cửa 5
  voice_new.wav
  style.ass         # cửa 6
  preview.jpg
long-tieng/out/<id>_final.mp4   # cửa 7
```

### Làm theo lát (code) — không 7 cửa một PR

| Lát | Cửa | Xong khi… |
|-----|-----|-----------|
| **A** ✅ | 1 + 7 thu hẹp | Upload video → tách wav → mux lại **cùng tiếng gốc** ra mp4 |
| **B** ✅ | 2 | Whisper → hiện/sửa `orig.srt` |
| **C** ✅ | 3 + 4 | Dịch (Ollama hoặc dán tay) → editor → `final.srt` |
| **D** ✅ | 5 | TTS từng cue + slider tốc độ/âm lượng → nghe `voice_new.wav` |
| **E** ✅ | 6 + 7 đủ | Preview vị trí + burn + thay audio → mp4 có sub + giọng mình |

Lát A trước STT vì mux/burn là chỗ dễ gãy máy; lát E mới là “đủ đăng”. Tab TTS hiện tại không đụng cho đến khi lát D tái sử dụng `synthesize_*`.

### Không làm trong wizard này

- Studio lớp B (chữ phóng theo từ), nhép miệng, hàng trăm template CapCut.
- Tách vocal/nhạc (Demucs), tải URL, cloud render, ElevenLabs/Edge.
- Codex trong UI khách.
- Drag chữ trên khung preview (cửa xuất). Timeline kéo từng từ = lớp B, sau MVP.

Hai lớp chữ (đừng gộp một phát):

| Lớp | User thấy | Kỹ thuật | Khi nào |
|-----|-----------|----------|---------|
| **A. Sub đăng bài** | Một dòng/câu dưới hoặc giữa khung | SRT + burn ffmpeg (ASS) | MVP — phải có |
| **B. Studio caption** | Nói tới đâu chữ hiện / phóng / đổi màu tới đó | Word/phrase timestamp + template hiệu ứng (Remotion / HTML→video / ASS karaoke) | Sau khi A ổn |

“Như studio / CapCut post” = chủ yếu **lớp B**. Lớp A đã đủ đăng; B là khác biệt cảm giác.

**Mẫu lớp B đơn giản nhất — “1 từ / lần”** (tham chiếu Shorts `BgdnY8PaaxY`, 608×1080, đo 2026-10-07):

- Mỗi lúc **đúng 1 từ**, IN HOA, cắt cứng sang từ sau (không pop/scale/fade). Từ ngắn (“OF”) chỉ ~1–2 frame; khoảng nghỉ giữ từ cũ, không trống.
- Font condensed nét đậm hơi nghiêng kiểu Bangers / Luckiest Guy; chữ hoa cao ~3,4% chiều cao khung (≈65 px ở 1080×1920 → cỡ font ~90 px).
- Màu xanh neon `#40F858` + viền đen mỏng + **bóng đen mờ rộng** (glow tối) — đọc được trên cả nền sáng lẫn tối, không cần hộp nền.
- Tâm chữ ~26% từ trên, giữa ngang — tránh tay/súng phía dưới. Nhược: đè HUD game (“ROUND SURVIVED”).
- Cần mốc **từng từ** (`faster-whisper word_timestamps=True`); render = mỗi từ 1 PNG trong concat hiện có của `burn.py`.

| Việc | CapCut | App mình | Ghi chú |
|------|--------|----------|---------|
| Ghép voice vào video | Có | **MVP** | ffmpeg mux + atempo |
| Sub vị trí cố định | Có | **MVP** | bottom / mid |
| Cắt / nối đoạn | Có | **MVP** | trim + nối, không keyframe |
| Chữ hiệu ứng theo lời | Có (auto captions) | **Sau MVP** | cần mốc từ + 1–2 template |
| Dịch tiếng | AI | Codex/LLM **ngoài** | `codex.md` |
| Clone giọng | Không lõi | VieNeu local | trần chất lượng bên dưới |
| Nhép miệng / effect đầy | Có | **Không** gần | HeyGen tầng khác |

Không làm sớm: hàng trăm template CapCut, cloud render, nhét Codex vào UI khách.

### Lộ trình “thành công trước” (map sang wizard)

1. **TTS ổn** — đang `app.py` (tab TTS). Wizard tái dùng ở cửa 5.
2. **ffmpeg mux** — lát A (cửa 1 + 7 hẹp).
3. **STT + dịch + duyệt** — lát B–C (cửa 2–4). Dịch **trong app** (Ollama) hoặc dán từ ngoài; không còn “bắt buộc Codex trước khi mở app”.
4. **Giọng + tốc độ + volume** — lát D (cửa 5).
5. **Lớp A burn + vị trí** — lát E (cửa 6–7). **MVP xong ở đây.**
6. **Trim / nối** — sau MVP.
7. **Lớp B (studio)** — 1 template chữ theo từ; chỉ khi đã đăng được clip thật.

Mỗi lát phải ra file (wav/srt/mp4) rồi mới lát sau.

Đối thủ kiểu [HypeTransVideo trên Shop HP Tools](https://shophptools.com/tool-details/hypetransvideo-tool-dich-va-long-tieng-video-chuyen-nghiep): trang bán tool MMO, không mô tả kỹ thuật. Cùng họ hàng [pyVideoTrans](https://github.com/jianchang512/pyvideotrans) / HeyGen: STT → dịch → TTS → mux. **Không clone/crack license shop đó.** Làm pipeline sạch, BYOK hoặc model local.

## Surfaces

- Demo GUI: `long-tieng/app.py` → Gradio `http://127.0.0.1:7860`
- Hàng nút luôn hiện: **1 Video · 2 Sub · 3 Dịch · 4 Giọng · 5 Xuất · TTS · Cài đặt**.
- Cửa 5 Xuất: kéo chữ trên khung preview; font / màu chữ / cỡ chữ; checkbox nền + màu nền.
- Job: `long-tieng/jobs/<id>/` — `orig.srt` `target.srt` `final.srt` `cues/` `voice_new.wav` `subs/*.png`
- Xuất: `long-tieng/out/<id>_final.mp4`
- Cần `ffmpeg` + `faster-whisper` + VieNeu. Ollama tùy (không có thì dán SRT dịch). Lần đầu tải model, cần mạng.

## Hành vi & ràng buộc

### Cách app kiểu [HypeTransVideo](https://shophptools.com/tool-details/hypetransvideo-tool-dich-va-long-tieng-video-chuyen-nghiep) chạy

Trang shop **không** mô tả kỹ thuật (template MMO). Không soi được binary từ URL. Tool desktop “dịch + lồng tiếng” bán ở VN (HypeTrans, pyVideoTrans, DHB Render, MMO Auto Translate) cùng một máy:

**User thấy:** chọn video (hoặc URL) → chọn ngôn ngữ + giọng → bấm chạy → nhận mp4 có sub + thuyết minh, thường giữ nhạc nền.

**Máy làm (không có phép màu):**

```text
video/URL
  → tải (nếu URL) + ffmpeg tách tiếng
  → (tuỳ chọn) tách vocal / nhạc nền
  → STT: Whisper local hoặc API → SRT gốc + mốc thời gian
  → dịch từng câu → SRT đích (Google / LLM cloud / Ollama)
  → TTS từng câu bằng giọng đã chọn (Edge-TTS, ElevenLabs, hoặc clone local)
  → atempo nếu câu đọc dài hơn đoạn gốc
  → trộn vocal mới + nhạc nền + burn sub → mp4
```

Giọng “có sẵn” = danh sách voice ID (Edge/Azure) **hoặc** file wav mẫu trong thư mục refs. Nhấn nhá = model TTS + dấu câu, không phải app nhớ từ vựng. License shop = khóa dùng phần mềm, **không** phải engine dịch/đọc.

Không crack license. Không clone GUI shop.

### Pipeline (làm sạch, cùng họ hàng — không copy shop)

1. Tách audio — code (ffmpeg)
2. Speech → text + timestamp — model local (faster-whisper) hoặc API. ChatGPT free **không** nghe file
3. Dịch text — BYOK Gemini/OpenAI (tab Cài đặt) sau khi khóa `orig.srt`; Ollama tùy; hoặc dán SRT. Không nhét Codex SDK.
4. TTS giọng đã lưu — model **trên máy**. Chỗ khó + tốn
5. Canh SRT, vị trí sub, mux — code (ffmpeg)

Khó thật: timestamp, nhấn nhá, sub không đè mặt. Nhép miệng (HeyGen) = tầng khác, đắt, không cần cho ngách khóa học/tin.

Clip Auto News **không** lấy voice gốc (bài báo → JSON → TTS). Khác tool này.

### “Lưu giọng sẵn rồi đọc nhấn nhá — không AI ngoài”

**AI ngoài** = ChatGPT / Gemini / ElevenLabs / Edge-TTS (Edge vẫn gọi Microsoft). **Tắt được.**

**Không AI gì cả** thì không đọc câu mới tự nhiên. IVR cũ: thu sẵn từng câu. Câu chưa thu → câm hoặc robot.

Cách làm thật — **AI chạy trong máy**, giọng nằm trong app:

| Lưu gì | Lúc chạy | Nhấn nhá từ đâu |
|--------|----------|-----------------|
| Thư mục `long-tieng/voice/` (demo) / `refs/`: wav 3–10s | Text mới + file ref → TTS local (VieNeu) | Model copy tempo/cao độ từ clip mẫu; dấu câu trong bản dịch |
| Fine-tune vài giờ audio **giọng mình** (có consent) | Chỉ text, không gửi cloud | Ổn định hơn zero-shot; vẫn là model |
| SSML / ngắt câu (code) | Chèn `break`, tốc độ theo `.?!` | Nhấn nhá **thô**. Không thay model |

Tiếng Việt local (2026): VieNeu-TTS (đang dùng, Mac/ONNX dễ), Gwen-TTS / G-OmniVoice / KhanhTTS-OmniVoice (thường **xịn hơn clone** theo claim WER/SIM nhưng cần **NVIDIA CUDA**, không “pip một phát” như `vieneu` trên Mac), V-TTS (nhẹ CPU, chất lượng thấp hơn studio). Piper: nhanh, **không** clone giọng.

Nhấn nhá khá = clip mẫu **đã nói có nhịp** (không đọc đều) + bản dịch có dấu câu. Không có bảng “từ này nhấn thanh 3” đủ cho mọi câu.

**Trần chất lượng:** VieNeu zero-shot clone (clip 3–8s) **không ngang** studio TTS thương mại. Constraint sản phẩm: **local only** — không VBee/ElevenLabs/Edge trả phí. Ngon hơn trong máy = (1) giọng sẵn của VieNeu nếu không cần clone (2) mẫu nói 3–8s sạch đúng mặc định model (3) model local khác / fine-tune nhiều giờ. Không kỳ vọng clone 8s = VBee.

Chỉ clone giọng **mình / khách có quyền**. Không clone giọng người khác từ YouTube.

**Mẫu clone = nói, không phải hát.** VieNeu lấy `ref_codes` từ clip → copy nhịp/cao độ/âm sắc. File bài hát (melody, rung, hát kéo) → TTS hay “rên”, run, không đọc chữ rõ. Dùng 3–8s **nói sạch**, một người, không nhạc nền.

**Đoạn đọc khi thu mẫu (chọn 1 câu, ~5–8s):** nói rõ, tốc độ bình thường, có dấu câu. Không thì thầm, không ASMR, không nhạc.

- `Xin chào, tôi đang thử giọng nói tự nhiên. Hôm nay trời mát, làm việc rất dễ chịu.`
- `Chào bạn, đây là bản ghi giọng của tôi. Xin hãy nghe rõ từng từ và ngắt nghỉ.`
- `Tôi đọc chậm, rõ ràng: một, hai, ba. Sau đó kết thúc bằng câu cảm ơn.`

Tránh: hát, đọc đều robot, chỉ “à ừ”, clip có tiếng cười/rên/beat. Cùng một mic/không gian với lúc sẽ dùng giọng.

Ngách: một thể loại, ~5 kênh cùng format. Không “dịch mọi video” / tool MMO trùm.

## Phụ thuộc

`docs/features/auto-news-video.md`, `docs/features/saas-ngach.md` (#4). Bài test: không làm feature này.

**Đọc hiểu kỹ thuật / nghệ thuật (điều chỉnh sản phẩm):** `docs/features/long-tieng-kien-thuc.md`.

## Code chính

- `long-tieng/app.py` — Gradio: tab Cài đặt + Video cửa 1–7 + TTS.
- `long-tieng/settings.py` — BYOK Gemini/OpenAI, lưu `settings.json`.
- `long-tieng/video_job.py` — job dir, ffprobe, tách wav, mux roundtrip.
- `long-tieng/stt.py` — faster-whisper → `orig.srt`.
- `long-tieng/translate.py` — Gemini/OpenAI/Ollama hoặc dán SRT; khóa `final.srt`.
- `long-tieng/dub.py` — phong cách đọc (preset tốc độ + EQ/`aecho`) + atempo + volume + ghép `voice_new.wav`.
- `long-tieng/burn.py` — Pillow PNG theo cue; concat 1 luồng chữ + overlay 1 lần; VideoToolbox khi xuất.
- `long-tieng/requirements.txt` — `vieneu`, `gradio`, `torch`, `faster-whisper`, `pillow`.
- Chạy: `cd long-tieng && source .venv/bin/activate && python app.py`
- Lần đầu TTS / Whisper: tải model. Homebrew ffmpeg không libass → overlay PNG.

## Changelog

- 2026-10-07: cửa Xuất — tùy chỉnh **font / màu chữ / cỡ chữ** (Pillow + preview HTML); vị trí kéo giữ như cũ.
- 2026-10-07: phân tích caption Shorts `BgdnY8PaaxY` → ghi mẫu lớp B “1 từ / lần” (font, màu, bóng, vị trí, cách làm bằng word timestamp).

- 2026-08-27: cửa Giọng + tab TTS — dropdown **Phong cách đọc** (Bình thường / Truyện ma / Tin tức / Kể chuyện / Năng lượng). Truyện ma = chậm, rõ, hơi vang; FX ffmpeg sau khi canh cue.
- 2026-08-21: copy/dán sub rồi nhảy Giọng — không bắt khóa cửa 3 nếu đã khóa orig; dán Gemini lệch số câu thì ghép mốc gốc. Cửa 2 ghi `target.srt` bản gốc.
- 2026-08-21: dán Gemini / Dùng bản dán / Dịch API khóa luôn `final.srt`; sang 4 Giọng hoặc Đọc+ghép tự khóa nếu ô dịch còn chữ. Tách tiếng lại **giữ job** (không mất bản khóa). Cửa 2 không nhét orig vào ô dịch.
- 2026-08-21: GitHub chỉ code — `voice/*.mp3` không commit; clone máy khác thì copy `voice/` riêng (USB/Drive) hoặc tải YupVox.
- 2026-08-20: nguồn mẫu giọng = [YupVox TTS](https://yupvox.com/text-to-speech) → file `voice/` (không nhét API vào app).
- 2026-08-18: README giới thiệu workspace + studio (`README.md`, `long-tieng/README.md`).
- 2026-08-18: TTS không cắt đuôi cue (nuốt chữ); tăng tốc + tràn ~0.3s sang câu sau; báo số câu dài hơn mốc.
- 2026-08-18: Đọc + ghép — hiện `Đọc k/n`; cache TTS theo câu (đổi tốc độ không đọc lại 149 lần).
- 2026-08-18: cửa Dịch — nút Dùng bản dán + gửi file .srt/.txt (copy Gemini chat rồi nhét lại).
- 2026-08-18: dịch lô 50–100 câu dạng SRT; prompt chỉ dịch thoại, giữ số/timestamp, không lời dẫn; time lấy từ file gốc.
- 2026-08-18: dịch nhanh hơn — một phát như chat (≤90 Gemini / ≤280 OpenAI); lô to hơn; OpenAI song song; Gemini 429 nhảy OpenAI luôn nếu có key.
- 2026-08-18: dịch lỗi/429 → tự đổi model rồi máy kia (Gemini↔OpenAI, Ollama cuối) nếu đã lưu key; không đứng chết một máy.
- 2026-08-18: dịch Gemini tuần tự + retry 429 (free `gemini-3.5-flash` 5 req/phút); không dump JSON quota.
- 2026-08-18: cửa xuất — kéo chữ gắn `js_on_load` của khung preview (Gradio 6); viền xanh trước đó chỉ CSS nên kéo không được.
- 2026-08-18: dịch lô 32 câu, Gemini/OpenAI song song 3 luồng — không worker process; kẹt ở API không phải main thread.
- 2026-08-18: cửa Giọng — nút Nghe thử 1 câu (mẫu / câu đầu sub) + cache TTS; slider tốc độ/volume áp ffmpeg.
- 2026-08-18: xuất nhanh hơn — 1 overlay (concat PNG) + h264_videotoolbox; bỏ N lớp overlay từng câu.
- 2026-08-18: cửa xuất — kéo thả chữ trên khung preview; checkbox nền + chọn màu nền.
- 2026-08-18: nav = hàng nút 1 Video…Cài đặt (bỏ Tabs `...`); luôn có nút về nhập video.
- 2026-08-18: gọi Gemini/OpenAI dùng certifi — Python.org trên Mac hay lỗi SSL local issuer.
- 2026-08-18: tab Cài đặt BYOK Gemini/OpenAI (key + model); dịch đọc settings; Ollama tùy; `settings.json` gitignore.
- 2026-08-18: `demo.load` Ollama phải nằm trong `gr.Blocks` — gọi ngoài context thì Gradio AttributeError.
- 2026-08-18: lát C–E — Ollama/dán dịch + khóa `final.srt`; TTS từng cue tốc độ/volume; Pillow overlay vị trí + xuất `_final.mp4` (ffmpeg brew không libass).
- 2026-08-18: lát B — faster-whisper local → `orig.srt` sửa tay + khóa; model tiny/base/small; chưa dịch.
- 2026-08-18: lát A — tab Video, `video_job.py` tách `audio_orig.wav` + mux `_roundtrip.mp4`; video câm chặn; cần ffmpeg.
- 2026-08-18: chốt wizard 7 cửa (nhập → STT → dịch → duyệt → giọng tốc độ/volume → vị trí sub → xuất); lát A→E; Ollama hoặc dán tay, không Codex trong app.
- 2026-08-16: trỏ lộ trình đọc `long-tieng-kien-thuc.md`.
- 2026-08-16: tách chữ lớp A (sub đăng) vs B (studio hiệu ứng theo lời); B sau khi 1–5 đã xuất được clip.
- 2026-08-16: hướng sản phẩm = edit đủ đăng YT (voice+sub+cắt); Codex ngoài dịch; lộ trình 5 bước thành công trước.
- 2026-08-16: siết clone (wav 8s + infer chuẩn + fp32/MPS + giọng sẵn); vẫn không y chang mẫu.
- 2026-08-16: enroll lại ≤8s đoạn rõ nhất; file ~34s trước đó bị nhét full → đớ (không phải thiếu 8s).
- 2026-08-16: so sánh local thay VieNeu — OmniVoice/Gwen thường ngon hơn nhưng CUDA; Mac thì VieNeu/V-TTS dễ hơn.
- 2026-08-16: chốt local-only; bỏ hướng API trả phí; nâng chất = giọng sẵn VieNeu / mẫu 8s / model khác.
- 2026-08-16: trần VieNeu clone vs VBee; ngon = BYOK giọng sẵn hoặc fine-tune, không kỳ vọng 8s thắng studio.
- 2026-08-16: script thu mẫu 3 câu (~5–8s nói sạch).
- 2026-08-16: mẫu bài hát → clone “hát/rên”; cần clip nói 3–8s sạch.
- 2026-08-16: clone file < 10 phút load hết; bỏ cắt 8s của VieNeu.
- 2026-08-16: thêm m4a/aac/ogg/mp4…; đổi sang wav bằng afconvert (Mac) hoặc ffmpeg.
- 2026-08-16: nút Thêm file giọng = UploadButton (thêm được nhiều file, không kẹt sau lần đầu).
- 2026-08-16: demo GUI Gradio + thư mục `voice/`; VieNeu local; chưa pipeline video.
- 2026-08-16: tách code vs AI; không chuyển bài test sang tool này.
- 2026-08-16: HypeTransVideo = cùng pipeline; giọng lưu `refs/` + TTS local; nhấn nhá từ model/mẫu, không hết AI.
- 2026-08-16: luồng chạy app kiểu shop (STT→dịch→TTS→mux). Trang HP Tools không có spec nội bộ.
