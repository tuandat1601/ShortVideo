# Mẫu Rule — Docs Protocol (mọi web app)

> **File mẫu.** Copy phần «Nội dung `.mdc`» vào  
> `.cursor/rules/docs-protocol.mdc`  
> rồi **thay bảng Feature paths** bằng đường dẫn thật của dự án.
>
> Nguyên tắc: [`PRINCIPLES.example.md`](./PRINCIPLES.example.md).

---

## Nội dung copy vào `.cursor/rules/docs-protocol.mdc`

```markdown
---
description: Đọc docs theo Architecture index trước khi code; cập nhật MD feature khi sửa
alwaysApply: true
---

# Docs protocol

## Bắt đầu mọi task
1. Đọc `docs/ARCHITECTURE.md` (index / bản đồ feature).
2. Từ bảng Feature map / Feature paths, đọc **chỉ** các `docs/features/*.md` (và `docs/sites/*.md` nếu có) khớp task — tối đa khoảng 1–3 file.
3. Không đọc toàn bộ `docs/` và không đọc file kiến trúc/legacy dài trừ khi index chưa cover hoặc user chỉ định.
4. Brand / domain / multi-site → đọc thêm `docs/sites/<ten>.md` nếu có.

## Khi sửa hoặc thêm tính năng
1. Sửa code theo phạm vi task.
2. **Bắt buộc** cập nhật MD feature tương ứng trong cùng task.
3. Feature mới: tạo `docs/features/<ten>.md` (template: Mục đích / Surfaces / Hành vi / Code chính / Changelog), **và** thêm một hàng vào bảng trong `docs/ARCHITECTURE.md` **và** bảng Feature paths bên dưới (giữ rule đồng bộ với index).
4. Cuối task: thêm 1–5 dòng vào `## Changelog` (`YYYY-MM-DD: …`).

## Feature paths (đọc / ghi) — ĐIỀN CHO TỪNG DỰ ÁN

> Xóa các hàng placeholder; giữ bảng gọn, đúng codebase.

| Việc / từ khóa | Doc (đọc & ghi) | Code chính |
|----------------|-----------------|------------|
| Routing / URL resolve | `docs/features/routing.md` | `…` |
| Trang chủ / landing shell | `docs/features/homepage.md` | `…` |
| Auth / session | `docs/features/auth.md` | `…` |
| Nội dung / CMS / blog | `docs/features/content.md` | `…` |
| Form lead / contact | `docs/features/leads.md` | `…` |
| SEO | `docs/features/seo.md` | `…` |
| Admin / back-office UX | `docs/features/admin.md` | `…` |
| Frontend assets / UI kit | `docs/features/frontend.md` | `…` |
| Deploy / CI / infra | `docs/features/deploy.md` | `…` |
| Seed / fixtures / bootstrap | `docs/features/seed.md` | `…` |
| Site / brand này | `docs/sites/<ten>.md` | `…` |

## Prompt chat mới
User chỉ cần nêu mục tiêu (+ tên feature nếu biết). Lấy ngữ cảnh từ MD, không yêu cầu dán lịch sử chat cũ.
Nếu doc và code lệch: ưu tiên code đang chạy, rồi cập nhật MD cho khớp.

## Giới hạn
Rule này là protocol (+ bảng path). Chi tiết hệ thống nằm ở `docs/ARCHITECTURE.md` và feature MD — không mở rộng file rule bằng dump kiến trúc.
```

---

## Bản map phẳng (sau khi đã tạo file — sửa list cho khớp dự án)

```text
docs/ARCHITECTURE.md
docs/features/routing.md
docs/features/homepage.md
docs/features/auth.md
docs/features/content.md
docs/features/leads.md
docs/features/seo.md
docs/features/admin.md
docs/features/frontend.md
docs/features/deploy.md
docs/features/seed.md
docs/sites/<ten>.md
```

## Legacy (không always-read)

Đánh dấu rõ trong dự án, ví dụ:

```text
architecture.md          # legacy
docs-old/                # legacy
```

---

## Tuỳ chọn: rule theo glob (secondary)

Không thay protocol `alwaysApply`. Ví dụ:

```markdown
---
description: Khi sửa backend, đối chiếu feature docs liên quan
globs: "**/*.{py,ts,go}"
alwaysApply: false
---

# Backend ↔ docs

Trước khi sửa sâu: mở `docs/ARCHITECTURE.md`, chọn feature MD khớp file đang đụng.
Sau khi sửa: cập nhật Changelog của MD đó.
```

Đổi `globs` theo stack (`app/**/*.tsx`, `internal/**/*.go`, …).

---

## Checklist gắn rule vào repo mới

- [ ] Đã có `docs/ARCHITECTURE.md` với Feature map
- [ ] Đã copy protocol vào `.cursor/rules/docs-protocol.mdc` với `alwaysApply: true`
- [ ] Đã thay bảng Feature paths bằng path thật (không để nguyên placeholder nếu gây nhầm)
- [ ] Nội dung rule **không** chứa dump toàn bộ kiến trúc
- [ ] Team thống nhất: task đụng feature → đụng luôn file MD tương ứng

---

## Gợi ý prompt user

```text
Làm theo docs protocol.
Task: <mô tả ngắn>.
```

```text
Sửa feature <tên>. Đọc ARCHITECTURE index rồi đúng feature MD trước khi code; xong thì cập nhật Changelog.
```
