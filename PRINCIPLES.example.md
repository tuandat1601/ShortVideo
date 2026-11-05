# Nguyên tắc thiết kế: Docs-as-Source-of-Truth cho Agent

> **File mẫu.** Copy vào dự án web app mới, đổi tên bỏ `.example`, rồi điền Feature map / đường dẫn cho codebase thật.
>
> - `PRINCIPLES.example.md` → `docs-system/PRINCIPLES.md` hoặc `docs/PRINCIPLES.md`
> - Kèm [`rule.example.md`](./rule.example.md) → `.cursor/rules/docs-protocol.mdc`

Tài liệu mô tả cách tổ chức **Architecture (index) + Rule (protocol) + MD theo tính năng/site** để mỗi chat/task mới tự nắm tình hình mà **không cần paste lịch sử chat**, đồng thời **không tốn token** vì nhồi cả kiến trúc dài vào rule.

---

## 1. Vấn đề cần giải

| Cách cũ | Hệ quả |
|---------|--------|
| Chat dài mang suốt context dự án | Tốn token, chat mới mất ngữ cảnh |
| Một file architecture/ke hoạch khổng lồ luôn gắn vào rule | Mỗi turn đều trả phí cả nghìn dòng |
| Sửa code xong không ghi doc | Chat sau phải “đoán” lại từ code |

**Mục tiêu:** Sự thật nằm ở **file MD có cấu trúc**. Chat chỉ là phiên làm việc ngắn: đọc → sửa → ghi lại → đóng.

---

## 2. Ba lớp tài liệu (bắt buộc tách)

```text
┌─────────────────────────────────────────────────────────┐
│  RULE (protocol)                                         │
│  .cursor/rules/*.mdc                                     │
│  → Luôn inject vào agent                                 │
│  → CHỈ quy trình: đọc gì, sửa gì, ghi lại gì             │
│  → Ngắn; có thể kèm bảng path feature (compact)          │
│  → Không nhét dump kiến trúc                             │
└──────────────────────────┬──────────────────────────────┘
                           │ trỏ tới
                           ▼
┌─────────────────────────────────────────────────────────┐
│  ARCHITECTURE (index)                                    │
│  docs/ARCHITECTURE.md                                    │
│  → Bản đồ: feature/site → file MD + file code            │
│  → Stack + flow tổng quan 1 đoạn                         │
│  → Agent đọc ĐẦU MỖI TASK                                │
└──────────────────────────┬──────────────────────────────┘
                           │ chọn 1–N file
                           ▼
┌─────────────────────────────────────────────────────────┐
│  FEATURE / SITE MD (chi tiết)                            │
│  docs/features/*.md                                      │
│  docs/sites/*.md   (optional: multi-site / brand pack)   │
│  → Chỉ load phần khớp task                               │
│  → Cập nhật BẮT BUỘC khi sửa feature đó                  │
└─────────────────────────────────────────────────────────┘
```

| Lớp | Inject thế nào | Nội dung được phép |
|-----|----------------|--------------------|
| **Rule** | `alwaysApply: true` | Protocol, cấm/nên, (optional) bảng path |
| **Architecture** | Đọc khi bắt đầu task | Bảng map, 1 đoạn stack, quy ước |
| **Feature/Site MD** | Đọc theo map | Model/API, route, UI, ràng buộc, changelog |

**Quy tắc vàng:** Rule = *cách làm việc*. Architecture = *ở đâu*. Feature MD = *chi tiết là gì*.

---

## 3. Tiết kiệm token — nguyên tắc cứng

1. **Không** put toàn bộ architecture vào rule `alwaysApply`.
2. Index `ARCHITECTURE.md` giữ **≤ ~100–150 dòng** (chủ yếu là bảng).
3. Mỗi feature MD **≤ ~150 dòng**; changelog chỉ bullet ngắn.
4. Mỗi task chỉ đọc **1–3** feature MD, không đọc cả `docs/features/`.
5. File kiến trúc/kế hoạch cũ dài → đánh dấu **legacy** — không đọc trừ khi index chưa cover hoặc user chỉ định.
6. Chat mới chỉ cần: *mục tiêu + (optional) tên feature*. Context lấy từ MD.

---

## 4. Cấu trúc thư mục chuẩn

```text
docs/
  ARCHITECTURE.md              # INDEX — bắt buộc
  features/
    <ten-tinh-nang>.md         # một file = một bề mặt kỹ thuật
  sites/                       # optional
    <ten-site-hoac-brand>.md

.cursor/rules/
  docs-protocol.mdc            # từ rule.example.md
```

Tên feature: kebab-case ổn định (`routing.md`, `auth.md`, `deploy.md`, …).

---

## 5. Chọn feature nào cần doc riêng

Chia theo **bề mặt sửa thường xuyên**, không theo từng field model.

| Nên tách MD riêng khi… | Ví dụ (minh họa — đổi theo app) |
|------------------------|----------------------------------|
| Có URL/API riêng + regression dễ | routing, auth, payments, webhooks |
| Composition UI/page phức tạp | homepage, dashboard shell |
| Domain model + admin UX đặc thù | catalog, bookings, org-tree |
| Ops / deploy độc lập | deploy, CI, seed/fixtures |
| Brand / multi-tenant | `docs/sites/<name>.md` |

**Không** tách MD cho mọi utility nhỏ — ghi vào feature đang dùng chúng.

---

## 6. Nội dung `docs/ARCHITECTURE.md` (index)

Phải có:

1. **Stack / flow** — vài dòng.
2. **Feature map:**

   `| Khi làm việc về… | Đọc doc | Code chính |`

3. **Quy ước:** sửa feature X → cập nhật MD X; feature mới → tạo MD + thêm dòng bảng (+ cập nhật rule nếu rule có bảng path).

### Mẫu bảng

```markdown
| Khi làm việc về… | Đọc doc | Code chính |
|------------------|---------|------------|
| Routing | docs/features/routing.md | … |
| Auth | docs/features/auth.md | … |
| Deploy | docs/features/deploy.md | … |
| Brand / site này | docs/sites/<ten>.md | … |
```

---

## 7. Template feature MD

```markdown
# Feature: <Tên>

## Mục đích
Một đoạn.

## Surfaces
- URL / route / API:
- Model / schema:
- View / handler:
- Template / UI / client:
- Admin / CMS (nếu có):

## Hành vi & ràng buộc
…

## Phụ thuộc
…

## Code chính
- `path/to/file`

## Changelog
- YYYY-MM-DD: …
```

### Template site (optional)

```markdown
# Site: <Tên>

## Nhận diện
- Domain, locale, timezone
- Brand tokens — trỏ file theme/CSS

## Pack / module bật
- Danh sách feature MD dùng cho site này

## Khác biệt so với core
…

## Changelog
- YYYY-MM-DD: …
```

---

## 8. Flow mỗi task / chat mới

```text
1. Rule đã inject → đọc docs/ARCHITECTURE.md
2. Từ bảng map → mở đúng docs/features/*.md (+ sites/ nếu cần)
3. Đọc code được liệt kê
4. Thực thi task
5. Cập nhật MD feature + Changelog
6. Feature mới → tạo MD + cập nhật index (+ rule path table nếu có)
7. Đóng chat
```

Prompt gợi ý:

```text
Làm theo docs protocol.
Task: <mô tả ngắn>.
```

---

## 9. Cách áp dụng sang dự án web app mới

1. Copy `PRINCIPLES.example.md` + `rule.example.md` vào repo.
2. Tạo `docs/ARCHITECTURE.md` — viết bảng map theo codebase thật (5–10 hàng là đủ lúc đầu).
3. Tạo stub `docs/features/*.md` cho bề mặt hay đụng nhất.
4. Copy nội dung protocol trong `rule.example.md` → `.cursor/rules/docs-protocol.mdc` (`alwaysApply: true`).
5. Điền bảng Feature paths trong rule cho khớp dự án (bỏ hàng placeholder).
6. Đánh dấu file kiến trúc dài cũ (nếu có) là legacy.

### Checklist onboard

- [ ] Có `docs/ARCHITECTURE.md` với Feature map
- [ ] Có feature MD cho phần hay sửa
- [ ] Rule protocol `alwaysApply: true`, không kèm dump kiến trúc
- [ ] Changelog trong mỗi feature MD
- [ ] Legacy docs ghi chú “không always-read”

---

## 10. Anti-patterns

| Sai | Đúng |
|-----|------|
| Rule 500 dòng = toàn bộ architecture | Rule ≤ ~80–120 dòng protocol (+ bảng path gọn) |
| Một `docs.md` khổng lồ | Index mỏng + nhiều feature MD |
| Sửa code, quên MD | Cùng task cập nhật MD |
| Mỗi chat `@` hết `docs/` | Chỉ index + 1–3 feature |
| Hai nguồn truth lệch nhau không chủ đích | Một nguồn kỹ thuật; user guide trỏ sang hoặc mirror có chủ đích |

---

## File kèm

| File | Dùng để |
|------|---------|
| [`rule.example.md`](./rule.example.md) | Mẫu rule/protocol + chỗ điền Feature paths |
