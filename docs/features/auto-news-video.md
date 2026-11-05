# Feature: Auto News Video

## Mục đích

Tool trong clip TikTok: URL bài báo → Gemini JSON (Shorts) → TTS + render local. **Không** dùng Veo. Khác bài test: họ copy prompt sang Gemini tay; bài test gọi API qua `chayNhiemVu()`.

Không biến thành mốc bài test.

## Surfaces

- App demo: `localhost:3847` — form script JSON, Tạo video
- TikTok: https://www.tiktok.com/@tvcdevcntt/video/7673168474528550164 (fetch 403; oembed `#xh #laptrinhvien #cntt`)
- File đúng clip: https://drive.google.com/file/d/12yC5192K550YoNm6HKUp8dFXF5bBlYse — `7392638589623570448.mp4`, ~100s, 1024×576, 4.8MB
- Local lúc chat: `/Users/tuandat/Downloads/7392638589623570448.mp4`
- Bio kênh: Gemini Pro / Antigravity PRO; nhận làm web/tool

**Không dùng** clip Bandicam (user bảo bỏ): https://drive.google.com/file/d/1QzX_TmWPnHDKuPoqSf0vWzv1hP1jWD7m — Django admin `phaplymiennam.vn`. Không liên quan sản phẩm này.

## Hành vi & ràng buộc

```text
Bài báo VnExpress (URL)
  → Copy prompt Gemini (công thức JSON Shorts 9:16)
  → Dán gemini.google.com (acc Pro của họ)
  → Gemini trả 1 object JSON (metadata + scenes hook/body)
  → Dán script.json trong app
  → TTS + ảnh + compose HTML + render
  → video.mp4 + voice.mp3 + script.txt (CapCut)
```

Demo: bài thù lao 300 triệu/tháng (vnexpress). Video ~49s. Chữ lớn hook. Watermark `@tvcdevcntt`.

Ngách nếu làm sau: một loại fanpage (luật / tin địa phương), không “tin tức mọi creator”. BYOK Gemini. Không bán acc. Xem `docs/features/saas-ngach.md`.

## Phụ thuộc

`docs/features/codex.md` — không nhét Codex vào app kiểu này. `docs/features/long-tieng.md` — pipeline khác (có lấy voice gốc).

## Code chính

- Chưa có repo trong APPAI. Nguồn sự thật = clip Drive + mô tả trên.

## Changelog

- 2026-08-16: xem clip; phân biệt JSON+TTS vs Veo; Bandicam bỏ.
- 2026-08-16: chuyển từ dump `architec.md` mục B sang feature MD.
