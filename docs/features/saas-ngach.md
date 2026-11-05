# Feature: SaaS ngách

## Mục đích

Chiến lược chen thị trường: một việc lặp của một nghề, không tool trùm. Nguồn: [Khánh Hùng — SaaS / phần mềm / sản phẩm số](https://www.youtube.com/watch?v=56OY0I34toI). Ứng viên ngách **chưa chốt**.

## Surfaces

- YouTube `56OY0I34toI` — Đời sống lập trình / Mona
- Phân phối: group nghề, không nhóm lập trình viên

## Hành vi & ràng buộc

Video (để không lệch): (1) công nghệ không cần siêu cấp (2) đừng khoe nhóm dev/gamer (3) người bán được thường không phải dev — ở ngách rồi thuê viết (4) một vấn đề đúng ngách; VN không trả tiền cho tiện lợi trừ ship đồ ăn (5) đừng sợ đã có người làm — ~100 triệu dân.

Công thức một dòng: **[nghề X] + [việc lặp Y] + [mất tiền/rủi ro nếu sai] + [đang trả bằng Z]**. Thiếu Y/Z = slogan.

Chen = một output, một nhịp. Ở lại ngách rồi nới việc kế bên **cùng nghề**. Không bán “nhanh hơn ChatGPT”.

Case video: Excel công thức kiểm toán bán lại mỗi đổi chính sách (vài chục triệu/tháng); website tôn giáo 2013 vẫn bán; GV tiếng Anh clone hệ thống cho giảng viên khác.

### Ứng viên (2026-08-16, chưa chọn)

Gần skill phiên này:

| # | Ngách | Wedge | Đang trả |
|---|--------|-------|----------|
| 1 | Shop mỹ phẩm / TPCN / mẹ bé: 10 caption/ngày không claim chữa bệnh | Máy đề xuất bài test + bộ cấm kỵ ngành | Thuê viết / ads bị gỡ |
| 2 | Fanpage luật / công chứng: 1 short/ngày từ URL tin pháp lý | Auto News, chữ nghề | Thuê content / intern sai |
| 3 | Người bán khóa học: quay A–Z → cắt ầm, sub, hook/body/CTA | Clip Sang; BYOK; Codex ngoài app | CapCut vài giờ hoặc thuê editor |
| 4 | Sub+TTS **một** thể loại clip | `long-tieng.md` | Thuê dịch + editor |

Cần người nghề: (5) file mỗi lần đổi thông tư (6) Zalo nhắc tái khám phòng nha (7) nhật ký nghiệm thu thầu nhỏ.

Chọn cái **7 ngày nhắn được 10 người**. Gợi ý: #1 nếu giữ content shop; #3 nếu đi video. #8 nếu đi khảo sát cửa hàng gần nhà (không cần cộng sự). #5–7 bỏ nếu chưa có cộng sự nghề.

Không làm: AI mọi shop, video mọi creator, acc rẻ, Codex-trong-app. Không clone Super App (WeChat, Meituan, i深圳, xe chia sẻ, tủ đồ).

### Điều tra Thâm Quyến (2026-08-16)

Cảm giác “rất hiện đại” = **hạ tầng + Super App**, không phải một app nhỏ. Steal **việc lặp**, không steal giao diện.

| Lớp | Thâm Quyến | VN đang làm | Làm phần mềm nhỏ? |
|-----|------------|-------------|-------------------|
| Hạ tầng | WeChat/Alipay QR, metro mặt, i深圳 8000+ dịch vụ | MoMo/ZaloPay, VNeID còn rời | Không — vốn + nhà nước |
| Đời sống | Meituan 25–35 phút, 团购 salon/nha/spa, tủ đồ, xe chia sẻ | Grab/ShopeeFood; đặt chỗ = Zalo | Không marketplace / hardware |
| Tòa nhà | Mini-program 物业: khách QR, phí, báo hỏng | Zalo group + sổ bảo vệ + Excel | Chỉ nếu có BQL |
| Phòng khám | 挂号 + nhắc tái khám trong WeChat | Lễ tân gọi / Zalo tay | Có — khớp #6 |
| Việc làm | DingTalk/Feishu duyệt phép, HĐĐT | Zalo + Excel + kế toán thuê | ERP đã đông; HĐĐT có MISA |
| Chợ phần cứng | Hoa Cường Bắc: báo giá linh kiện nhanh | Tiệm sửa viết tay, cãi bảo hành | Có — form + phiếu |

Ứng viên lấy từ Thâm Quyến (cùng công thức, stack form + công thức + AI JSON):

| # | Ngách | Wedge | Đang trả |
|---|--------|-------|----------|
| 8 | Salon / spa / nha 1–3 ghế: lịch + cọc + nhắc, giảm no-show | Không làm Meituan. Form giờ + QR cọc; AI soạn tin nhắc / gói giờ | Lễ tân + inbox Zalo; ghế trống = mất slot |
| 9 | Tiệm sửa điện thoại / laptop: báo giá + phiếu bảo hành | Hoa Cường Bắc thu nhỏ. Form lỗi + linh kiện → phiếu; AI không bịa giá | Viết tay / cãi bảo hành |
| 10 | BQL chung cư: sổ khách + thông báo + báo hỏng | 物业 bỏ Super App. Một tòa, một việc | Excel + bảo vệ; cycle bán dài |

#8 gần “thấy hiện đại” nhất mà vẫn bán được một mình. #6 được Thâm Quyến xác nhận (复诊) — chỉ mở nếu có nha sĩ. #10 để sau.

## Phụ thuộc

Stack đủ: Next + Postgres — `docs/features/bai-test.md`. Codex giao hàng: `docs/features/codex.md`.

## Code chính

- Chưa có sản phẩm ngách trong APPAI. Bài test không biến ngách thành mốc.

## Changelog

- 2026-08-16: năm ý video Khánh Hùng; công thức ngách; 7 ứng viên chưa chốt.
- 2026-08-16: gộp `ngach.md` (copy lệch chỗ) vào feature MD.
- 2026-08-16: điều tra Thâm Quyến — steal việc không steal Super App; thêm #8 salon no-show, #9 phiếu sửa máy, #10 BQL.
