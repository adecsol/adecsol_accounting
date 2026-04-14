# l10n_vn_b03dn_direct_report

Module Odoo 18: **Báo cáo lưu chuyển tiền tệ — mẫu B03-DN, phương pháp trực tiếp** (Thông tư 200/2014). Chỉ tiêu và quy tắc gán số liệu được **cấu hình** qua model `l10n.vn.b03dn.template` / `l10n.vn.b03dn.line`, không cố định trong code Python.

**Tài liệu HTML (mở trực tiếp trong trình duyệt):**

- [doc/b03dn_template_config_user.html](doc/b03dn_template_config_user.html) — **cấu hình template B03-DN** cho **kế toán** (không cần code).
- [doc/b03dn_template_config_dev.html](doc/b03dn_template_config_dev.html) — **cấu hình template** cho **developer** (field, constraint, XML, engine).
- [doc/developer_guide.html](doc/developer_guide.html) — **Odoo developer**: tổng quan module, engine, mở rộng, file tham chiếu.
- [doc/lctt_tt200_calculation_management.html](doc/lctt_tt200_calculation_management.html) — **tóm tắt cách có con số** (B03-DN / TT200) cho **lãnh đạo / non-tech**.
- [doc/lctt_tt200_calculation_technical.html](doc/lctt_tt200_calculation_technical.html) — **chi tiết kỹ thuật** (fragment, pattern, engine).

## Tổng quan luồng dữ liệu

1. **Chọn tập tài khoản tiền** trong kỳ báo cáo (`date_from` … `date_to`), chỉ các bút toán **đã post**.
2. Lấy mọi dòng sổ (`account.move.line`) thuộc các TK đó → gọi là **dòng tiền**.
3. Với từng dòng tiền, trong cùng `account.move`, xác định **TK đối ứng** (các dòng khác trên chứng từ). Nếu một lần có **nhiều đối ứng** cùng phía (ví dụ nhiều TK Có đối ứng một dòng Nợ tiền), số tiền được **phân bổ** theo tỷ lệ Nợ/Có của từng đối ứng (tương tự logic S01-DN trong `l10n_vn_s01dn_report`).
4. Mỗi cặp *(dòng tiền, phần đối ứng đã phân bổ)* tạo một **fragment**: chiều vào/ra, mã TK đối ứng, `account` đối ứng, số tiền, id dòng tiền (để drill-down).
5. Các fragment được so khớp lần lượt với các dòng template kiểu **leaf** (theo `sequence`). **Một fragment chỉ gán vào tối đa một chỉ tiêu leaf** — chỉ tiêu **đầu tiên** thỏa điều kiện được cộng dồn (xem mục *Ưu tiên rule*).
6. Các chỉ tiêu **opening_cash**, **fx_adjustment** tính riêng bằng SQL/truy vấn.
7. Các chỉ tiêu **aggregate** cộng dồn số và gộp tập `aml_ids` theo biểu thức `sum_expression` (ví dụ `01+02+…+20`).
8. Chỉ tiêu **none** chỉ hiển thị, luôn **0** và không tham gia so khớp fragment.

## Nguồn “tiền và tương đương tiền”

| Cấu hình | Cách xác định TK |
|----------|------------------|
| Trên **template**: `cash_account_ids` có giá trị | Chỉ các tài khoản được chọn (lọc theo công ty). |
| Để trống | Tất cả TK mã `111%`, `112%`, `113%` của công ty **+** các TK trong `res.company.b03dn_cash_equiv_account_ids` (tương đương tiền ngắn hạn, ví dụ tiểu khoản 128). |

Chỉ các phát sinh **trên các TK này** trong kỳ mới sinh fragment; các TK khác không đi vào báo cáo trực tiếp qua luồng này.

## Chiều tiền và mẫu TK đối ứng (leaf)

- **Tiền vào**: dòng tiền **Nợ &gt; 0**, Có ≈ 0. Engine so khớp **`credit_account_patterns`** với mã TK đối ứng phía **Có** (cột «TK Có» hướng dẫn TT200). Số vào báo cáo: **+amount** × `amount_multiplier`.
- **Tiền ra**: dòng tiền **Có &gt; 0**, Nợ ≈ 0. So khớp **`debit_account_patterns`** với đối ứng phía **Nợ** («TK Nợ»). Số: **−amount** × `amount_multiplier`.

## Mẫu tài khoản (`debit_account_patterns`, `credit_account_patterns`)

- Danh sách phân tách dấu **phẩy** (ví dụ `511%,131%`).
- Hậu tố **`%`**: khớp **tiền tố** mã TK đối ứng.
- Không có `%`: khớp **đúng mã**.
- **`exclude_tag_ids`**: nếu pool thẻ (theo `tag_source`) chứa một thẻ loại trừ → leaf không nhận fragment.

Nếu đối ứng có **nhiều mã**, hệ thống thử từng mã; **một mã** khớp là đủ (sau khi qua điều kiện thẻ).

## Thẻ (`tag_ids`, `exclude_tag_ids`, `tag_source`, `tag_match_mode`)

- **`tag_ids`**: chỉ fragment thỏa điều kiện thẻ mới được gán.
- **`exclude_tag_ids`**: có một trong các thẻ này trong pool → bỏ qua leaf.
- **`tag_source`**: `counterpart_account` (mặc định) = thẻ trên **`account.account`** đối ứng; `cash_line` = thẻ trên dòng tiền; `either` = ưu tiên dòng tiền rồi TK đối ứng.
- **`tag_match_mode`**: `all` / `any`.

Lưu ý: leaf **bị bỏ qua** nếu sau parse **không** còn mẫu TK **và** không có `tag_ids` (rule rỗng).

## Domain bổ sung (`extra_domain`)

Chuỗi Python là **domain Odoo** (list), `safe_eval` trên `account.move.line` của **dòng tiền**. Áp dụng **sau** khi đã khớp pattern/thẻ.

## Ưu tiên rule (leaf)

`leaf_lines` sắp theo `sequence`, `id`. Với **mỗi fragment**, engine duyệt rule theo thứ tự đó; **dừng ngay** khi khớp rule đầu tiên.

Hệ quả:

- Rule **cụ thể** (tag, mẫu hẹp) nên đặt **sequence nhỏ hơn** rule tổng quát.
- Hai rule có thể khớp cùng một giao dịch nếu chỉ một được “ăn” fragment — cần hiệu chỉnh thứ tự hoặc mẫu để tránh nhầm chỉ tiêu.

## Các loại chỉ tiêu (`line_kind`)

| `line_kind` | Cách lấy số | Drill-down (HTML) |
|-------------|-------------|-------------------|
| **none** | Luôn 0. | Không. |
| **leaf** | Cộng dồn fragment khớp rule; `aml_ids` = các **dòng tiền** (`cash_aml_id`). | Có, theo `id` dòng tiền. |
| **aggregate** | `sum_expression`: cộng số các mã (ví dụ `20+30+40`); `aml_ids` = hợp các mã con. | Có (gộp nhiều dòng). |
| **opening_cash** | `SUM(debit - credit)` của các TK tiền (cùng tập như trên), `date < date_from`, posted. | Không (số tổng hợp). |
| **fx_adjustment** | Trong kỳ, các dòng AML mà `account_id.code` khớp `fx_account_patterns` (mặc định `413%`); số = **tổng `balance`** các dòng đó. | Có (theo id các dòng tỷ giá). |

**Lưu ý biểu thức tổng:** Mọi mã trong `sum_expression` phải **tồn tại** là một dòng template cùng `code`. Nếu thiếu mã, engine sẽ **bỏ qua** bước cộng đó cho đến khi bạn thêm dòng (kể cả `line_kind = none` với số 0) hoặc chỉnh lại biểu thức.

## Bảng tham chiếu — dữ liệu mẫu `b03dn_template_tt200_direct.xml`

Các giá trị dưới đây là **mặc định** trong module; doanh nghiệp có thể chỉnh trên UI.

### Phần I — HĐ kinh doanh (leaf)

| Mã | Chiều tiền | Đối ứng (mẫu mặc định) | Ghi chú |
|----|-------------|------------------------|---------|
| 01 | Vào (Nợ tiền) | `511%`, `131%` | Doanh thu / thu từ KH… |
| 02 | Ra (Có tiền) | `331%` + thẻ `B03-DN — Chi trả NCC` trên **TK đối ứng** | Tách khỏi chi 331 khác nếu gắn thẻ. |
| 03 | Ra | `334%` | Chi NLĐ. |
| 04 | Ra | `635%`, `242%`, `335%` | Lãi vay / chi phí tài chính. |
| 05 | Ra | `3334%` | TNDN hiện hành. |
| 06 | Vào | `515%`, `811%`, `717%` | Thu khác HĐKD. |
| 07 | Ra | `632%`… trừ `635%` trong loại trừ | Chi khác HĐKD; exclude tránh trùng lãi vay. |

**20** — `aggregate`: mặc định `01+02+03+04+05+06+07` (theo `sum_expression` trong XML).

### Phần II — HĐ đầu tư

| Mã | Chiều | Mẫu đối ứng (mặc định) | Ghi chú |
|----|-------|-------------------------|---------|
| 21 | Ra | `211%`… + thẻ **mua TSCĐ** trên TK đối ứng | |
| 22 | Vào | `711%`, `214%` | Thanh lý TSCĐ… |
| 23 | Ra | `128%`, `228%`, `229%` | Chi cho vay / công cụ nợ… |
| 24 | Vào | `128%`, `228%` | Thu hồi… |
| 25 | Ra | `221%`, `222%`, `228%` | Góp vốn đầu tư ra ngoài. |
| 26 | Vào | `221%`, `222%` | Thu hồi góp vốn. |
| 27 | Vào | `515%`, `635%` | Lãi / cổ tức thu. |

**30** — `aggregate`: mặc định `21+22+23+24+25+26+27`.

### Phần III — HĐ tài chính

| Mã | Chiều | Mẫu đối ứng (mặc định) |
|----|-------|-------------------------|
| 31 | Vào | `411%` |
| 32 | Ra | `411%`, `412%` |
| 33 | Vào | `341%`, `343%`, `344%` |
| 34 | Ra | `341%`, `343%`, `344%` |
| 35 | Ra | `212%`, `214%`, `342%` |
| 36 | Ra | `421%`, `338%` |

**40** — `aggregate`: mặc định `31+32+33+34+35+36`.

### Phần IV — Tổng hợp

| Mã | Loại | Logic mặc định |
|----|------|----------------|
| 50 | aggregate | `20+30+40` |
| 60 | opening_cash | Số dư đầu kỳ (trước `date_from`) của nhóm TK tiền. |
| 61 | fx_adjustment | Tổng `balance` AML trong kỳ, TK khớp `413%` (hoặc `fx_account_patterns`). |
| 70 | aggregate | `50+60+61` |

Các dòng **H1–H4** là `line_kind = none` (chỉ tiêu đề phần).

## Báo cáo và drill-down

- **QWeb / HTML**: số trên chỉ tiêu có liên kết tới danh sách `account.move.line` khi có `aml_ids` (dùng container OCA `account_financial_report`).
- **XLSX**: cùng cấu trúc số; không nhất thiết hyperlink trong Excel.

## Phụ thuộc chính

`accounting_adecsol`, `account_financial_report`, `report_xlsx`, `mis_builder`, `mis_builder_cash_flow` (stack OCA); engine B03 **không** đọc KPI MIS — chỉ dùng `account.move.line` và cấu hình template.

## Cài đặt

Thêm thư mục module vào `--addons-path`, cài **B03-DN — Lưu chuyển tiền tệ (phương pháp trực tiếp, cấu hình)**. Menu B03-DN trong localization Adecsol mở **wizard** chọn kỳ và template.

Cấu hình template: **Kế toán → Cấu hình → B03-DN templates** (hoặc tương đương theo menu đã định nghĩa).
