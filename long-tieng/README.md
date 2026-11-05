<div align="center">

# Studio lồng tiếng

Sub + giọng trên **máy bạn** → mp4 đăng YouTube / TikTok.

VieNeu · Whisper · ffmpeg · Gradio

[http://127.0.0.1:7860](http://127.0.0.1:7860)

</div>

---

## Chạy

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
brew install ffmpeg   # một lần, Mac
python app.py
```

| Cần | Ghi chú |
|-----|---------|
| Python 3.10+ | 3.14 ok |
| ffmpeg | Homebrew **không** libass — app đốt chữ bằng PNG |
| Mạng lần đầu | Tải Whisper + VieNeu |

## Wizard

`1 Video → 2 Sub → 3 Dịch → 4 Khóa → 5 Giọng → 6 Chữ → 7 Xuất`

- **Dịch:** copy ô trái → Gemini → dán ô phải → **Dùng bản dán** (khóa luôn). Nút **Dịch (API)** nếu có key.
- **Giọng:** local, từng câu sub (khớp timestamp). Chọn **phong cách đọc** (vd. Truyện ma). Ô trạng thái: `Đọc 12/149`
- **Chữ:** kéo ô trên khung preview — không kéo video Mp4 cuối

Chi tiết: [`docs/features/long-tieng.md`](../docs/features/long-tieng.md) (trong workspace APPAI).

## Clone sang máy khác

Repo GitHub **không** chứa file giọng (cả thư mục `voice/*.mp3` ~60MB) và **không** chứa `settings.json` (key).

```bash
git clone git@github.com:tuandat1601/AutoSubVideo.git
cd AutoSubVideo
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp settings.example.json settings.json   # dán key Gemini/OpenAI
```

Rồi copy nguyên thư mục `voice/` từ máy này sang (USB / Drive). Không có file mp3 thì cửa Giọng trống — tải mẫu [YupVox TTS](https://yupvox.com/text-to-speech) bỏ vào `voice/`.

## Thư mục job

```text
jobs/<id>/   source, orig.srt, final.srt, cues/, voice_new.wav
out/         <id>_final.mp4
voice/       mẫu clone
settings.json   BYOK — không commit
```
