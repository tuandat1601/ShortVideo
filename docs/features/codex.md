# Feature: Codex vs app khách

## Mục đích

Trả lời: *Codex đưa vào app được à?* Nguồn: [clip Sang — cài tool edit video](https://www.youtube.com/watch?v=bFNgTOraIwA).

**Được theo nghĩa clip: Codex đứng ngoài, trên máy khách, thợ cài + thợ sửa.** Không nhét agent vào sản phẩm để user bấm Sinh.

## Surfaces

- [Codex desktop](https://openai.com/index/introducing-the-codex-app/) (ChatGPT, macOS/Windows)
- SDK (dev/ops của mình, không phải form khách): https://developers.openai.com/codex/sdk

## Hành vi & ràng buộc

Clip: zip source → cài Codex (khuyên Plus $20 — gói chính thức) → New project trỏ thư mục → *“Hãy cài app trong thư mục cho tôi”* → chạy app local → dán **API key ChatGPT** (BYOK). Video thô trong `library/`, nhạc trong `music/`. App gọi ChatGPT (sub, cắt ầm, ảnh). Sửa thumbnail = **chat lại Codex**, Allow, Codex sửa code.

| Nghĩa “đưa vào app” | Được? |
|---------------------|--------|
| Giao source + khách mở Codex cài/sửa | Có — kênh giao hàng, mỗi máy một kiểu |
| Nhét Codex SDK vào SaaS để chủ shop ra lệnh sửa code | Kỹ thuật có; sai sản phẩm (trái đóng gói công thức) |
| Đưa Codex vào bài test / worker | Không |

Rủi ro clip: Allow = đụng máy khách; sửa lung tung gãy app; source copy được; không phải SaaS hosted.

Chốt: bài test không Codex. Sản phẩm sau: form + BYOK. Mình dùng Codex lúc **viết code**. Không hướng dẫn acc Plus/Codex rẻ hơn giá chính thức.

## Phụ thuộc

`docs/features/bai-test.md` (đóng gói công thức). `docs/features/saas-ngach.md` (#3 talking-head). `docs/features/auto-news-video.md`.

## Code chính

- Không nhúng Codex runtime vào APPAI hay bài test.

## Changelog

- 2026-08-16: Codex ngoài app; BYOK ChatGPT trong app edit; không SDK trong form user.
- 2026-08-16: chuyển `codex.md` lệch chỗ sang feature MD.
