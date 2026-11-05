# Architecture — APPAI (index)

Đọc đầu mỗi task. Chi tiết: `docs/features/`. Protocol: `.cursor/rules/docs-protocol.mdc`. Thiết kế hệ docs: `docs/PRINCIPLES.md`.

Không phải tài liệu nộp bài test. Không nhét dump chat vào file này.

Giới thiệu repo (người đọc): [`README.md`](../README.md). Studio chạy được: [`long-tieng/README.md`](../long-tieng/README.md).

---

## Stack / flow

Hướng sản phẩm: Next.js (App Router) + PostgreSQL + Drizzle. App = form + công thức sẵn + AI trả JSON. Không chatbot, không Redis/Kafka.

Bài test (repo khác `ai-content-generator`):

```text
Trình duyệt → Next.js (Auth.js)
                ├─ createRepo(workspaceHienTai()) → PostgreSQL
                └─ chayNhiemVu() → jobs → workers/model → Gemini
```

Web không `fetch` Gemini.

---

## Feature map

| Khi làm việc về… | Đọc doc | Code / nguồn |
|------------------|---------|--------------|
| Bài test, mốc 4–5, lát dữ liệu, đóng gói prompt | `docs/features/bai-test.md` | `ai-content-generator`: `lib/studio/`, `loi-nhac-theo-nhiem-vu.js` |
| Auto News Video | `docs/features/auto-news-video.md` | TikTok `@tvcdevcntt`, Drive `12yC5192K550YoNm6HKUp8dFXF5bBlYse` |
| Lồng tiếng / sub / edit đủ đăng YT | `docs/features/long-tieng.md` | `long-tieng/app.py`; mẫu giọng: [YupVox TTS](https://yupvox.com/text-to-speech) → `voice/` |
| Kiến thức nền (TTS/ffmpeg/sub/studio) | `docs/features/long-tieng-kien-thuc.md` | đọc theo bước pipeline |
| SaaS ngách, ứng viên ngách | `docs/features/saas-ngach.md` | YouTube `56OY0I34toI` |
| Codex vs app khách | `docs/features/codex.md` | YouTube `bFNgTOraIwA` |

---

## Quy ước

- Sửa feature X → cập nhật MD X + Changelog cùng task.
- Feature mới → tạo MD + một hàng bảng trên + một hàng Feature paths trong rule.
- Acc AI giá rẻ / vượt quota / chia acc: không hướng dẫn. Lời sạch: API chính thức hoặc BYOK.
- Bài test: mốc 4 rồi 5. Không ôm Auto News, lồng tiếng, Codex-trong-app, acc rẻ.
- Ngách chưa chốt một cái — danh sách trong `saas-ngach.md`.

---

## Legacy (không always-read)

| File | Lý do |
|------|--------|
| `ghi-chep-chuyen-thoai/trao-doi.md` | Dump nguyên văn chat 2026-08-16 |
| `principle.md` / `rule.md` / `architec.md` (đã xóa) | Copy lộn mẫu PRINCIPLES/rule |

Cần nguyên văn → mở `trao-doi.md`. Làm việc hàng ngày → index + 1–3 feature MD.
