# Nguyên tắc thiết kế: Docs-as-Source-of-Truth cho Agent

Bản sống của [`PRINCIPLES.example.md`](../PRINCIPLES.example.md) cho repo APPAI. Không nhét chốt sản phẩm / dump chat vào file này.

Rule: [`.cursor/rules/docs-protocol.mdc`](../.cursor/rules/docs-protocol.mdc) (từ [`rule.example.md`](../rule.example.md)).

Tài liệu mô tả cách tổ chức **Architecture (index) + Rule (protocol) + MD theo tính năng** để mỗi chat/task mới tự nắm tình hình mà **không cần paste lịch sử chat**, đồng thời **không tốn token** vì nhồi cả kiến trúc dài vào rule.

---

## 1. Vấn đề cần giải

| Cách cũ | Hệ quả |
|---------|--------|
| Chat dài mang suốt context dự án | Tốn token, chat mới mất ngữ cảnh |
| Một file architecture/kế hoạch khổng lồ luôn gắn vào rule | Mỗi turn đều trả phí cả nghìn dòng |
| Sửa code xong không ghi doc | Chat sau phải “đoán” lại từ code |
| `principle.md` + `rule.md` + `architec.md` nhét cả chốt sản phẩm | Copy lộn mẫu — đã bỏ |

**Mục tiêu:** Sự thật nằm ở **file MD có cấu trúc**. Chat chỉ là phiên làm việc ngắn: đọc → sửa → ghi lại → đóng.

---

## 2. Ba lớp tài liệu (bắt buộc tách)

```text
┌─────────────────────────────────────────────────────────┐
│  RULE (protocol)                                         │
│  .cursor/rules/docs-protocol.mdc                         │
│  → Luôn inject vào agent                                 │
│  → CHỈ quy trình: đọc gì, sửa gì, ghi lại gì             │
│  → Ngắn; kèm bảng path feature (compact)                 │
│  → Không nhét dump kiến trúc / chốt nghề / ngách         │
└──────────────────────────┬──────────────────────────────┘
                           │ trỏ tới
                           ▼
┌─────────────────────────────────────────────────────────┐
│  ARCHITECTURE (index)                                    │
│  docs/ARCHITECTURE.md                                    │
│  → Bản đồ: feature → file MD + code / nguồn              │
│  → Stack + flow tổng quan 1 đoạn                         │
│  → Agent đọc ĐẦU MỖI TASK                                │
└──────────────────────────┬──────────────────────────────┘
                           │ chọn 1–N file
                           ▼
┌─────────────────────────────────────────────────────────┐
│  FEATURE MD (chi tiết)                                   │
│  docs/features/*.md                                      │
│  → Chỉ load phần khớp task                               │
│  → Cập nhật BẮT BUỘC khi sửa feature đó                  │
└─────────────────────────────────────────────────────────┘
```

| Lớp | Inject thế nào | Nội dung được phép |
|-----|----------------|--------------------|
| **Rule** | `alwaysApply: true` | Protocol, cấm/nên, bảng path |
| **Architecture** | Đọc khi bắt đầu task | Bảng map, 1 đoạn stack, quy ước |
| **Feature MD** | Đọc theo map | Model/API, ràng buộc, changelog |

**Quy tắc vàng:** Rule = *cách làm việc*. Architecture = *ở đâu*. Feature MD = *chi tiết là gì*.

Chốt sản phẩm (đóng gói công thức, ngách, Codex, bài test) nằm ở **feature MD**, không nằm ở PRINCIPLES hay rule.

---

## 3. Tiết kiệm token — nguyên tắc cứng

1. **Không** put toàn bộ architecture vào rule `alwaysApply`.
2. Index `ARCHITECTURE.md` giữ **≤ ~100–150 dòng** (chủ yếu là bảng).
3. Mỗi feature MD **≤ ~150 dòng**; changelog chỉ bullet ngắn.
4. Mỗi task chỉ đọc **1–3** feature MD, không đọc cả `docs/features/`.
5. Dump chat / file kiến trúc cũ → **legacy** — không đọc trừ khi index chưa cover hoặc user chỉ định.
6. Chat mới chỉ cần: *mục tiêu + (optional) tên feature*. Context lấy từ MD.

---

## 4. Cấu trúc thư mục (repo này)

```text
docs/
  PRINCIPLES.md                # file này — thiết kế hệ docs
  ARCHITECTURE.md              # INDEX — bắt buộc
  features/
    <ten-tinh-nang>.md

.cursor/rules/
  docs-protocol.mdc            # từ rule.example.md

ghi-chep-chuyen-thoai/
  trao-doi.md                  # LEGACY dump chat — không always-read
```

Tên feature: kebab-case (`bai-test.md`, `saas-ngach.md`, …).

---

## 5. Chọn feature nào cần doc riêng

Chia theo **bề mặt sửa thường xuyên**, không theo từng field model.

| Nên tách MD riêng khi… | File trong repo này |
|------------------------|---------------------|
| Bài test / mốc / ràng buộc chấm | `docs/features/bai-test.md` |
| Tool video tin tức đã xem | `docs/features/auto-news-video.md` |
| Pipeline lồng tiếng / sub | `docs/features/long-tieng.md` |
| Chiến lược ngách / SaaS | `docs/features/saas-ngach.md` |
| Codex vs app khách | `docs/features/codex.md` |

**Không** tách MD cho mọi utility nhỏ — ghi vào feature đang dùng chúng.

---

## 6. Nội dung `docs/ARCHITECTURE.md` (index)

Phải có:

1. **Stack / flow** — vài dòng.
2. **Feature map:** `| Khi làm việc về… | Đọc doc | Code chính |`
3. **Quy ước:** sửa feature X → cập nhật MD X; feature mới → tạo MD + thêm dòng bảng (+ cập nhật rule nếu rule có bảng path).

---

## 7. Template feature MD

```markdown
# Feature: <Tên>

## Mục đích
Một đoạn.

## Surfaces
- URL / route / API:
- Model / schema:
- Nguồn (video, repo, …):

## Hành vi & ràng buộc
…

## Phụ thuộc
…

## Code chính
- `path/to/file`

## Changelog
- YYYY-MM-DD: …
```

---

## 8. Flow mỗi task / chat mới

```text
1. Rule đã inject → đọc docs/ARCHITECTURE.md
2. Từ bảng map → mở đúng docs/features/*.md
3. Đọc code / nguồn được liệt kê
4. Thực thi task
5. Cập nhật MD feature + Changelog
6. Feature mới → tạo MD + cập nhật index (+ rule path table)
7. Đóng chat
```

Prompt gợi ý:

```text
Làm theo docs protocol.
Task: <mô tả ngắn>.
```

---

## 9. Anti-patterns (đã mắc, không lặp)

| Sai | Đúng |
|-----|------|
| `principle.md` = chốt nghề + docs protocol lẫn | PRINCIPLES = thiết kế hệ docs; chốt nghề = feature MD |
| `rule.md` dài = cấm phá bài test + protocol | Rule ≤ protocol + bảng path |
| `architec.md` dump cả phiên | Index mỏng + nhiều feature MD |
| Mỗi chat đọc hết `ghi-chep-chuyen-thoai/` | Chỉ index + 1–3 feature |
| Hai nguồn truth (ngach.md gốc + docs/features) | Một nguồn: `docs/features/` |

---

## File kèm

| File | Dùng để |
|------|---------|
| [`rule.example.md`](../rule.example.md) | Mẫu — đã copy vào `.cursor/rules/docs-protocol.mdc` |
| [`PRINCIPLES.example.md`](../PRINCIPLES.example.md) | Mẫu gốc — giữ ở root, không sửa khi làm việc hàng ngày |
