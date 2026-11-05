# Feature: Bài test — AI Content Generator

## Mục đích

Máy đề xuất nội dung cho chủ shop nhỏ (~10 bài Facebook/ngày). App đóng gói hồ sơ + công thức; user không tự viết prompt. Repo: `ai-content-generator` (không nằm trong APPAI).

## Surfaces

- URL: `/studio/de-xuat`, `/studio/bien-soan`, tab kịch bản, `/studio/hang-loat` (chưa), ảnh (chưa)
- AI: `chayNhiemVu()` → bảng `jobs` → `workers/model` → Gemini/OpenAI
- Auth: Auth.js v5, session DB, `/api/dev-login`
- Prompt hệ thống: `loi-nhac-theo-nhiem-vu.js` (không sửa `truongBatBuoc` / dòng `Cau truc:`)
- Dữ liệu shop: `DU_LIEU_NGUOI_DUNG`

## Hành vi & ràng buộc

**Đóng gói công thức:** user chọn việc (Fanpage, 10 ý) → app ghép hồ sơ + lát dữ liệu + lời nhắc sẵn → JSON. Chatbot = mỗi lần tự nghĩ prompt. App = form + chỗ trống.

**Mỗi lần Sinh đề xuất — không kéo hết DB:**

| Nguồn | Số | Đưa AI |
|-------|-----|--------|
| Hồ sơ | 1 | giọng, cấm kỵ |
| Trụ cột / chân dung / insight / sản phẩm | `list()` mặc định 200 | tên + mô tả |
| Bài đã đăng | 30, tóm tắt 280 ký tự | góc tiếp cận |
| Kênh ngoài | 40, `da_dung = false` | chỉ `kieuHook, chuDe, soChu, coCTA` — **không** `noiDung` |
| Bóc công thức trước Sinh | tối đa 20 bài chưa bóc | |

Cửa: `deXuatYTuong` trong `lib/studio/de-xuat.ts`. `thamKhao` không nguyên văn.

**Cấm phá (bài test):**

- Query web chỉ `createRepo(await workspaceHienTai())` — không import `db` vòng `lib/data-access/`
- Trụ cột / chân dung không khớp hồ sơ → `null`
- Hàm dựng lời nhắc không nhận nguyên văn bài kênh ngoài
- Ý từ tham khảo → `ideas.trend_signal_id`
- Web không `fetch` Gemini/OpenAI
- Không đổi tên export hợp đồng (`deXuatYTuong`, `khamPha`, `TI_LE_KHAM_PHA`, …)
- Tên biến/hàm/cột: tiếng Việt không dấu. `lib/` không import `next`

**Mốc ≠ điểm:** 5 bắt buộc + 2 phụ. “Đi tới mốc mấy” = 10%. Hợp đồng tên + 4 ràng buộc = 60%.

| Mốc | Việc | Trạng thái |
|-----|------|------------|
| 1 | `/studio/de-xuat` | Xong |
| 2 | `/studio/bien-soan` | Xong |
| 3 | Kịch bản quay (tab trên biên soạn) | Xong |
| 4 | `/studio/hang-loat` | **Tiếp theo** |
| 5 | Ảnh | Sau mốc 4 |
| phụ | chuỗi bài, so giọng | Không làm nếu hết giờ |

Mốc 4: `deXuatYTuong({ soLuong: 10 })` → enqueue `viet-bai` `cho: false`; worker 2 job song song; `raiTheoTruCot`; ~20% `khamPha`; idempotency (ngày + bề mặt + lần bấm). Chi tiết repo: `doc/feature/studio-hang-loat.md`.

Mốc 5: runner đang text-only; worker bỏ `sinh-anh`. Kẹt API ảnh thì cắt scope, ghi `GHI-CHU.md`.

**Không làm trong bài test:** Auto News, lồng tiếng, bán acc, Apify/ElevenLabs, gọi model từ `app/` hoặc client.

Nộp: commit theo mốc; `tsc` / test / build xanh; repo Private mời `SaLyTV`; video ≤ 10 phút + một quyết định kỹ thuật.

## Phụ thuộc

Repo bài test có `doc/` + `.cursor/rules/` riêng — khi làm **trong repo đó** ưu tiên doc đề bài. Thư mục APPAI chỉ nhật ký/hướng sản phẩm sau.

## Code chính

- `lib/studio/de-xuat.ts` — `gioiHan: 30`, `theoNguoiDung(nguoi, 40)`, `slice(0, 280)`
- `lib/data-access/contents.ts`, `tin-hieu-xu-huong.ts`, `crud-theo-workspace.ts`
- `lib/studio/boc-cong-thuc.ts` — `gioiHan = 20`
- `workers/model/`, `lib/model-runner/`

## Changelog

- 2026-08-16: chốt mốc 4 rồi 5; không ôm 7 mốc; lát 30/40/280; đóng gói công thức.
- 2026-08-16: chuyển từ `plan.md` / dump `architec.md` (copy lộn) sang feature MD.
