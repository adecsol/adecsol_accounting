#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sinh dữ liệu kiểm thử qua Odoo XML-RPC: đối tác + bút toán (S01-DN / B03-DN).

Dấu hiệu phân biệt với dữ liệu thật (lọc nhanh trong Odoo):
  - account.move.ref bắt đầu bằng tiền tố REF_PREFIX (mặc định: VN-ADECSOL-RPC-TEST/).
  - account.move.narration chứa NARRATION_MARKER.
  - Tên đối tác chứa PARTNER_MARKER ([VN-ADECSOL-RPC-TEST]).
  - Diễn giải dòng (account.move.line.name) luôn có LINE_NAME_MARKER.

Yêu cầu module / dữ liệu:
  - Bộ mã TT200 trên Odoo (ví dụ accounting_adecsol). Một số mã 3 số trong TT200
    có thể khớp tài khoản 4 số (911 -> 9110, 412 -> 4120, ...).
  - l10n_vn_b03dn_direct_report: nếu cài, script gắn thử thẻ dòng tiền [B03-DN] lên
    vài dòng tiền gửi NH (trường b03dn_cash_flow_tag_ids).

Chạy: chỉnh khối CONFIG bên dưới rồi:
  python3 tools/vn_report_rpc_test_seed.py

Mật khẩu: điền ODOO_PASSWORD trong CONFIG hoặc export ODOO_PASSWORD=...

HTTPS: CONFIG["SSL_VERIFY"] (mặc định False cho script seed). Ghi đè bằng
  export ODOO_SSL_VERIFY=1  (bật xác minh) hoặc ODOO_SSL_VERIFY=0 (tắt).
"""
from __future__ import annotations

import os
import ssl
import sys
import xmlrpc.client
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union

# --- Nhận diện dữ liệu test (đổi nếu cần, giữ đồng nhất khi lọc) ---
REF_PREFIX = "VN-ADECSOL-RPC-TEST/"
NARRATION_MARKER = "VN-ADECSOL-RPC-TEST — seed RPC cho B03-DN / S01-DN; xóa được."
PARTNER_MARKER = "[VN-ADECSOL-RPC-TEST]"
LINE_NAME_MARKER = "[VN-ADECSOL-RPC-TEST]"

# --- Cấu hình chạy trực tiếp (không dùng tham số dòng lệnh) ---
CONFIG: Dict[str, Any] = {
    "ODOO_URL": "http://116.118.47.15:8018",
    "ODOO_DB": "demo",
    "ODOO_USERNAME": "admin",
    # Để trống thì đọc biến môi trường ODOO_PASSWORD
    "ODOO_PASSWORD": "admin",
    "COMPANY_ID": 1,  # int hoặc None — ưu tiên hơn COMPANY_NAME
    "COMPANY_NAME": None,  # str hoặc None — tìm ilike khi không có COMPANY_ID
    # Khoảng ngày hạch toán: mỗi chứng từ (batch) một ngày, phân bổ đều trong [DATE_FROM, DATE_TO]
    "DATE_FROM": "2026-01-02",
    "DATE_TO": "2026-12-29",
    "BATCH_PAIRS": 18,
    "DRY_RUN": False,
    "WITH_B03_TAGS": False,
    # Chỉ mã TK bắt đầu bằng chuỗi này (vd "333"); để "" = tất cả mã trong TT200_CODES_RAW
    "ONLY_PREFIX": "",
    # True = kiểm tra chứng chỉ TLS; False = dev/self-sign (mặc định). Production: True + export ODOO_SSL_VERIFY=1
    "SSL_VERIFY": False,
}


def _coerce_bool(value: Any, default: bool) -> bool:
    """Chấp nhận bool hoặc chuỗi 'true'/'false'/...; None hoặc '' -> default."""
    if value is None or value == "":
        return default
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ("0", "false", "no", "off", "n"):
            return False
        if s in ("1", "true", "yes", "on", "y"):
            return True
        return default
    return bool(value)


def _ssl_verify_from_cfg_and_env(cfg: Mapping[str, Any]) -> bool:
    """True = xác minh chứng chỉ. Biến môi trường ODOO_SSL_VERIFY ghi đè CONFIG nếu được đặt."""
    env = os.environ.get("ODOO_SSL_VERIFY")
    if env is not None and str(env).strip() != "":
        return _coerce_bool(str(env).strip(), True)
    return _coerce_bool(cfg.get("SSL_VERIFY"), False)


def _insecure_tls_context() -> ssl.SSLContext:
    """Không xác minh chứng chỉ (chỉ dùng dev)."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _parse_cfg_date(value: Union[str, date, None], label: str) -> date:
    if value is None:
        raise ValueError("CONFIG thiếu %s" % label)
    if isinstance(value, date):
        return value
    s = str(value).strip()[:10]
    return date.fromisoformat(s)


def batch_posting_dates(date_from: date, date_to: date, n_batches: int) -> List[date]:
    """n_batches ngày (có thể trùng) từ date_from tới date_to gồm cả hai đầu."""
    if n_batches <= 0:
        return []
    if date_to < date_from:
        raise ValueError("DATE_TO phải >= DATE_FROM")
    span = (date_to - date_from).days
    if n_batches == 1:
        return [date_from]
    if span == 0:
        return [date_from] * n_batches
    return [
        date_from + timedelta(days=int(round(i * span / (n_batches - 1))))
        for i in range(n_batches)
    ]

# Mã tài khoản theo danh sách người dùng (TT200); thứ tự không ảnh hưởng logic.
TT200_CODES_RAW = """
111
1111
1112
1113
112
1121
1122
1123
113
1131
1132
121
1211
1212
1218
128
1281
1282
1283
1288
131
133
1331
1332
136
1361
1362
1363
1368
138
1381
1385
1388
141
151
152
153
1531
1532
1533
1534
154
155
1551
1557
156
1561
1562
1567
157
158
161
1611
1612
171
211
2111
2112
2113
2114
2115
2118
212
2121
2122
213
2131
2132
2133
2134
2135
2136
2138
214
2141
2142
2143
2147
217
221
222
228
2281
2288
229
2291
2292
2293
2294
241
2411
2412
2413
242
243
244
331
333
3331
33311
33312
3332
3333
3334
3335
3336
3337
3338
33381
33382
3339
334
3341
3348
335
336
3361
3362
3363
3368
337
338
3381
3382
3383
3384
3385
3386
3387
3388
341
3411
3412
343
3431
34311
34312
34313
3432
344
347
352
3521
3522
3523
3524
353
3531
3532
3533
3534
356
3561
3562
357
411
4111
41111
41112
4112
4113
4118
412
413
4131
4132
414
417
418
419
421
4211
4212
441
461
4611
4612
466
511
5111
5112
5113
5114
5117
5118
515
521
5211
5212
5213
611
6111
6112
621
622
623
6231
6232
6233
6234
6237
6238
627
6271
6272
6273
6274
6277
6278
631
632
635
641
6411
6412
6413
6414
6415
6417
6418
642
6421
6422
6423
6424
6425
6426
6427
6428
711
811
821
8211
8212
911
""".strip()


def _parse_codes() -> List[str]:
    out: List[str] = []
    for line in TT200_CODES_RAW.splitlines():
        code = line.strip()
        if code and code not in out:
            out.append(code)
    return out


TT200_CODES = _parse_codes()


def _is_liquid_code(code: str) -> bool:
    c = (code or "").strip()
    return c.startswith("111") or c.startswith("112") or c.startswith("113")


def _many2one_id(val: Any) -> Optional[int]:
    """XML-RPC search_read trả many2one dạng [id, name] hoặc chỉ id."""
    if val is None or val is False:
        return None
    if isinstance(val, (list, tuple)):
        if not val:
            return None
        return int(val[0])
    return int(val)


class OdooRPC:
    def __init__(
        self,
        url: str,
        db: str,
        username: str,
        password: str,
        *,
        ssl_context: Optional[ssl.SSLContext] = None,
    ) -> None:
        self.db = db
        self.username = username
        self.password = password
        self.uid: int = 0
        base = url.rstrip("/")
        kw: Dict[str, Any] = {}
        if ssl_context is not None:
            kw["context"] = ssl_context
        common = xmlrpc.client.ServerProxy(f"{base}/xmlrpc/2/common", **kw)
        self.models = xmlrpc.client.ServerProxy(f"{base}/xmlrpc/2/object", **kw)
        self.uid = int(common.authenticate(db, username, password, {}))
        if not self.uid:
            raise RuntimeError("Đăng nhập Odoo thất bại (kiểm tra db / user / password).")

    def execute(
        self,
        model: str,
        method: str,
        args: Optional[Sequence[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> Any:
        args = list(args or [])
        kwargs = dict(kwargs or {})
        return self.models.execute_kw(
            self.db,
            self.uid,
            self.password,
            model,
            method,
            args,
            kwargs,
        )


def _company_domain(company_id: Optional[int], company_name: Optional[str]) -> List[Any]:
    dom: List[Any] = []
    if company_id:
        dom.append(("id", "=", int(company_id)))
    if company_name:
        dom.append(("name", "ilike", company_name))
    return dom


def resolve_company(
    rpc: OdooRPC, company_id: Optional[int], company_name: Optional[str]
) -> Tuple[int, str]:
    dom = _company_domain(company_id, company_name)
    if not dom:
        dom = []
    ids = rpc.execute("res.company", "search", [dom], {"order": "id", "limit": 1})
    if not ids:
        raise RuntimeError("Không tìm thấy công ty (thiết lập --company-id hoặc --company-name).")
    cid = int(ids[0])
    rows = rpc.execute(
        "res.company",
        "read",
        [[cid]],
        {"fields": ["name"]},
    )
    name = (rows[0].get("name") or "") if rows else ""
    return cid, name


def resolve_account_id(rpc: OdooRPC, company_id: int, code: str) -> Optional[int]:
    """Khớp mã TK: chính xác theo công ty, sau đó prefix code (TT200 / COA Odoo)."""
    code = (code or "").strip()
    if not code:
        return None
    Account = "account.account"
    exact = rpc.execute(
        Account,
        "search",
        [[("company_ids", "in", [company_id]), ("code", "=", code)]],
        {"limit": 1},
    )
    print([[("company_ids", "in", [company_id]), ("code", "=", code)]])
    if exact:
        return int(exact[0])
    loose = rpc.execute(
        Account,
        "search",
        [[("company_ids", "in", [company_id]), ("code", "=ilike", code + "%")]],
        {"order": "code", "limit": 1},
    )
    if loose:
        return int(loose[0])
    return None


def pick_journal_and_liquid_account(
    rpc: OdooRPC, company_id: int
) -> Tuple[int, int, str]:
    """Ưu tiên sổ bank/cash có TK mặc định 112*/111*/113*."""
    journals = rpc.execute(
        "account.journal",
        "search_read",
        [
            [
                ("company_id", "=", company_id),
                ("type", "in", ("bank", "cash", "general")),
            ]
        ],
        {"fields": ["id", "type", "name", "default_account_id"], "order": "sequence,id"},
    )
    if not journals:
        raise RuntimeError("Không có account.journal cho công ty này.")

    def is_liquid_acc(acc_raw: Any) -> bool:
        acc_id = _many2one_id(acc_raw)
        if not acc_id:
            return False
        rows = rpc.execute(
            "account.account",
            "read",
            [[acc_id]],
            {"fields": ["code"]},
        )
        c = (rows[0].get("code") or "").strip() if rows else ""
        return _is_liquid_code(c)

    chosen = None
    for j in journals:
        if j["type"] in ("bank", "cash") and is_liquid_acc(j.get("default_account_id")):
            chosen = j
            break
    if not chosen:
        for j in journals:
            if j["type"] == "general":
                chosen = j
                break
    if not chosen:
        chosen = journals[0]

    acc_raw = chosen.get("default_account_id")
    aid = _many2one_id(acc_raw)
    if not aid:
        raise RuntimeError(
            "Journal %s không có default_account_id; cấu hình TK mặc định trên sổ."
            % chosen.get("name")
        )
    rows = rpc.execute(
        "account.account",
        "read",
        [[aid]],
        {"fields": ["code"]},
    )
    liq_code = (rows[0].get("code") or "").strip() if rows else ""
    jid = int(chosen["id"])
    return jid, aid, liq_code


def pick_equity_account_id(rpc: OdooRPC, company_id: int) -> Optional[int]:
    rows = rpc.execute(
        "account.account",
        "search_read",
        [
            [
                ("company_ids", "in", [company_id]),
                ("account_type", "=", "equity"),
            ]
        ],
        {"fields": ["id", "code"], "order": "code", "limit": 1},
    )
    if rows:
        return int(rows[0]["id"])
    return None


def pick_income_account_id(rpc: OdooRPC, company_id: int) -> Optional[int]:
    for atype in ("income", "income_other"):
        rows = rpc.execute(
            "account.account",
            "search_read",
            [
                [
                    ("company_ids", "in", [company_id]),
                    ("account_type", "=", atype),
                ]
            ],
            {"fields": ["id", "code"], "order": "code", "limit": 1},
        )
        if rows:
            return int(rows[0]["id"])
    return resolve_account_id(rpc, company_id, "511")


def load_b03dn_tag_map(rpc: OdooRPC) -> Dict[str, int]:
    """Trả về map '02' -> tag_id nếu module tag tồn tại."""
    rows = rpc.execute(
        "account.account.tag",
        "search_read",
        [[("name", "ilike", "[B03-DN][")]],
        {"fields": ["id", "name"], "limit": 200},
    )
    out: Dict[str, int] = {}
    for r in rows:
        name = r.get("name") or ""
        # Kỳ vọng: [B03-DN][02] ...
        if "[B03-DN][" in name:
            try:
                start = name.index("[B03-DN][") + len("[B03-DN][")
                end = name.index("]", start)
                code = name[start:end].strip()
                if code.isdigit() and code not in out:
                    out[code] = int(r["id"])
            except ValueError:
                continue
    return out


def ensure_partners(rpc: OdooRPC, company_id: int) -> Dict[str, int]:
    """Đối tác demo — id theo vai trò key: customer, supplier, employee, investor, lender."""
    Partner = "res.partner"
    marker_domain = [("name", "ilike", PARTNER_MARKER), ("company_id", "in", [False, company_id])]
    existing = rpc.execute(
        Partner,
        "search_read",
        [marker_domain],
        {"fields": ["id", "name", "ref"]},
    )
    by_ref = {r.get("ref"): int(r["id"]) for r in existing if r.get("ref")}

    def ensure(ref: str, name: str, customer_rank: int, supplier_rank: int) -> int:
        if ref in by_ref:
            return by_ref[ref]
        pid = rpc.execute(
            Partner,
            "create",
            [
                {
                    "name": name,
                    "ref": ref,
                    "company_id": company_id,
                    "is_company": True,
                    "customer_rank": customer_rank,
                    "supplier_rank": supplier_rank,
                }
            ],
        )
        by_ref[ref] = int(pid)
        return int(pid)

    partners = {
        "customer": ensure(
            "vn_rpc_test_cust",
            f"{PARTNER_MARKER} Khách hàng demo",
            1,
            0,
        ),
        "supplier": ensure(
            "vn_rpc_test_sup",
            f"{PARTNER_MARKER} Nhà cung cấp demo",
            0,
            1,
        ),
        "employee": ensure(
            "vn_rpc_test_emp",
            f"{PARTNER_MARKER} Nhân viên demo",
            0,
            0,
        ),
        "investor": ensure(
            "vn_rpc_test_inv",
            f"{PARTNER_MARKER} Nhà đầu tư demo",
            1,
            0,
        ),
        "lender": ensure(
            "vn_rpc_test_lender",
            f"{PARTNER_MARKER} Tổ chức tín dụng demo",
            0,
            1,
        ),
    }
    return partners


def _partner_for_index(partners: Dict[str, int], i: int) -> int:
    order = ("customer", "supplier", "employee", "investor", "lender")
    return partners[order[i % len(order)]]


def build_move_line_vals(
    *,
    company_id: int,
    target_acc_id: int,
    target_code: str,
    liquid_acc_id: int,
    equity_acc_id: Optional[int],
    income_acc_id: Optional[int],
    partner_id: int,
    seq: int,
    b03_tags: Dict[str, int],
    use_b03_tags: bool,
) -> List[Dict[str, Any]]:
    """Một cặp dòng cân đối cho mỗi TK mục tiêu."""
    amt = 1_000_000 + (seq % 500) * 10_000
    name = f"{LINE_NAME_MARKER} PS TK {target_code} (#{seq})"

    def cp_account() -> int:
        if target_acc_id == liquid_acc_id:
            if equity_acc_id:
                return equity_acc_id
            if income_acc_id:
                return income_acc_id
        return liquid_acc_id

    cp = cp_account()
    lines: List[Dict[str, Any]] = []

    if _is_liquid_code(target_code):
        # Tăng tiền mặt / NH: Nợ tiền, Có nguồn (vốn / DT)
        lines.append(
            {
                "account_id": target_acc_id,
                "partner_id": partner_id,
                "name": name + " — thu tiền (demo)",
                "debit": float(amt),
                "credit": 0.0,
            }
        )
        lines.append(
            {
                "account_id": cp,
                "partner_id": partner_id,
                "name": name + " — đối ứng",
                "debit": 0.0,
                "credit": float(amt),
            }
        )
        cash_line = lines[0]
    else:
        # Chi qua NH / tài khoản thanh khoản mặc định: Nợ TK đích, Có tiền
        lines.append(
            {
                "account_id": target_acc_id,
                "partner_id": partner_id,
                "name": name + " — ghi nhận (demo)",
                "debit": float(amt),
                "credit": 0.0,
            }
        )
        cash_line = {
            "account_id": cp,
            "partner_id": partner_id,
            "name": name + " — chi tiền (demo)",
            "debit": 0.0,
            "credit": float(amt),
        }
        lines.append(cash_line)

    if use_b03_tags and b03_tags and cash_line["account_id"] == liquid_acc_id:
        # Thẻ trong data module: 02,07,21,22,25,26,27,34,36 — chọn theo chiều tiền.
        if float(cash_line.get("credit") or 0) > 0:
            tid = b03_tags.get("02") or b03_tags.get("07") or b03_tags.get("34")
        else:
            tid = b03_tags.get("27") or b03_tags.get("26") or b03_tags.get("22")
        if tid:
            cash_line["b03dn_cash_flow_tag_ids"] = [(6, 0, [tid])]

    return lines


def chunk_list(items: Sequence[Any], size: int) -> List[List[Any]]:
    return [list(items[i : i + size]) for i in range(0, len(items), size)]


def line_model_has_b03dn_field(rpc: OdooRPC) -> bool:
    fg = rpc.execute("account.move.line", "fields_get", [], {"attributes": []})
    return "b03dn_cash_flow_tag_ids" in fg


def create_posted_moves(
    rpc: OdooRPC,
    *,
    company_id: int,
    journal_id: int,
    liquid_acc_id: int,
    equity_acc_id: Optional[int],
    income_acc_id: Optional[int],
    partners: Dict[str, int],
    specs: List[Tuple[str, int]],
    date_from: date,
    date_to: date,
    batch_pairs: int,
    dry_run: bool,
    use_b03_tags: bool,
    log: Callable[[str], None],
) -> List[int]:
    b03_field_ok = line_model_has_b03dn_field(rpc) if use_b03_tags else False
    if use_b03_tags and not b03_field_ok:
        log("Cảnh báo: model account.move.line không có b03dn_cash_flow_tag_ids — tắt gắn thẻ B03.")
    b03_tags = load_b03dn_tag_map(rpc) if (use_b03_tags and b03_field_ok) else {}
    if use_b03_tags and b03_field_ok and not b03_tags:
        log("Cảnh báo: không tìm thấy thẻ [B03-DN] — bỏ qua gắn tag (chưa nạp data?).")

    move_ids: List[int] = []
    batches = chunk_list(specs, max(1, batch_pairs))
    batch_dates = batch_posting_dates(date_from, date_to, len(batches))
    for bi, batch in enumerate(batches):
        line_commands: List[Any] = []
        for j, (code, acc_id) in enumerate(batch):
            seq = bi * batch_pairs + j + 1
            partner_id = _partner_for_index(partners, seq)
            for lv in build_move_line_vals(
                company_id=company_id,
                target_acc_id=acc_id,
                target_code=code,
                liquid_acc_id=liquid_acc_id,
                equity_acc_id=equity_acc_id,
                income_acc_id=income_acc_id,
                partner_id=partner_id,
                seq=seq,
                b03_tags=b03_tags,
                use_b03_tags=bool(use_b03_tags and b03_field_ok),
            ):
                line_commands.append((0, 0, lv))

        move_date = batch_dates[bi].isoformat()
        ref = f"{REF_PREFIX}BATCH-{bi+1:04d}"
        vals = {
            "company_id": company_id,
            "move_type": "entry",
            "journal_id": journal_id,
            "date": move_date,
            "ref": ref,
            "narration": NARRATION_MARKER,
            "line_ids": line_commands,
        }
        if dry_run:
            log(f"[dry-run] move ref={ref} date={move_date} lines={len(line_commands)}")
            continue
        mid = rpc.execute("account.move", "create", [vals])
        rpc.execute("account.move", "action_post", [[int(mid)]])
        move_ids.append(int(mid))
        log(
            f"Đã tạo & ghi sổ move id={mid} ref={ref} date={move_date} ({len(line_commands)} dòng)"
        )
    return move_ids


def run(cfg: Optional[Mapping[str, Any]] = None) -> int:
    cfg = dict(CONFIG if cfg is None else cfg)

    password = (cfg.get("ODOO_PASSWORD") or "") or os.environ.get("ODOO_PASSWORD", "")
    if not password:
        print("Thiếu mật khẩu: CONFIG['ODOO_PASSWORD'] hoặc biến ODOO_PASSWORD.", file=sys.stderr)
        return 2

    def log(msg: str) -> None:
        print(msg)

    url = cfg.get("ODOO_URL") or "http://localhost:8069"
    db = cfg.get("ODOO_DB") or ""
    if not db:
        print("Thiếu CONFIG['ODOO_DB'].", file=sys.stderr)
        return 2
    username = cfg.get("ODOO_USERNAME") or "admin"

    d0 = _parse_cfg_date(cfg.get("DATE_FROM"), "DATE_FROM")
    d1 = _parse_cfg_date(cfg.get("DATE_TO"), "DATE_TO")

    cfg_company_id = cfg.get("COMPANY_ID")
    cfg_company_name = cfg.get("COMPANY_NAME")
    batch_pairs = int(cfg.get("BATCH_PAIRS") or 18)
    dry_run = bool(cfg.get("DRY_RUN"))
    use_b03_tags = bool(cfg.get("WITH_B03_TAGS"))
    only_prefix = (cfg.get("ONLY_PREFIX") or "").strip()

    ssl_verify = _ssl_verify_from_cfg_and_env(cfg)
    ssl_ctx: Optional[ssl.SSLContext] = None
    if url.lower().startswith("https://") and not ssl_verify:
        ssl_ctx = _insecure_tls_context()
        print("Cảnh báo: không xác minh chứng chỉ TLS (SSL_VERIFY tắt).", file=sys.stderr)

    rpc = OdooRPC(url, db, username, password, ssl_context=ssl_ctx)
    company_id, cname = resolve_company(
        rpc,
        int(cfg_company_id) if cfg_company_id is not None else None,
        str(cfg_company_name) if cfg_company_name else None,
    )
    log(f"Công ty: {cname} (id={company_id})")
    log(f"Khoảng ngày hạch toán: {d0.isoformat()} … {d1.isoformat()}")

    journal_id, liquid_acc_id, liq_code = pick_journal_and_liquid_account(rpc, company_id)
    log(f"Sổ nhật ký id={journal_id}, TK thanh khoản mặc định id={liquid_acc_id} (mã {liq_code})")

    equity_id = pick_equity_account_id(rpc, company_id)
    income_id = pick_income_account_id(rpc, company_id)
    log(f"TK đối ứng khi TK mục tiêu là tiền: equity_id={equity_id} income_id={income_id}")

    partners = ensure_partners(rpc, company_id)
    log(f"Đối tác demo: {len(partners)} (ref vn_rpc_test_*)")

    codes = TT200_CODES
    if only_prefix:
        codes = [c for c in codes if c.startswith(only_prefix)]
        log(f"Lọc theo ONLY_PREFIX {only_prefix!r}: còn {len(codes)} mã")

    resolved: List[Tuple[str, int]] = []
    missing: List[str] = []
    for code in codes:
        aid = resolve_account_id(rpc, company_id, code)
        if aid:
            resolved.append((code, aid))
        else:
            missing.append(code)
    log(f"Đã khớp {len(resolved)}/{len(codes)} mã TK; thiếu {len(missing)}.")
    if missing:
        log("Mã không có trên hệ thống (bỏ qua): " + ", ".join(missing[:40]) + ("..." if len(missing) > 40 else ""))

    if not resolved:
        log("Không có dòng hợp lệ để tạo.")
        return 1

    n_batches = len(chunk_list(resolved, max(1, batch_pairs)))
    preview = batch_posting_dates(d0, d1, n_batches)
    log(f"Số chứng từ (batch): {n_batches}; ví dụ ngày: {preview[0].isoformat()} … {preview[-1].isoformat()}")

    create_posted_moves(
        rpc,
        company_id=company_id,
        journal_id=journal_id,
        liquid_acc_id=liquid_acc_id,
        equity_acc_id=equity_id,
        income_acc_id=income_id,
        partners=partners,
        specs=resolved,
        date_from=d0,
        date_to=d1,
        batch_pairs=batch_pairs,
        dry_run=dry_run,
        use_b03_tags=use_b03_tags,
        log=log,
    )

    log("")
    log("Hoàn tất. Lọc chứng từ test: ref bắt đầu bằng %r" % (REF_PREFIX,))
    log("Lọc đối tác test: tên chứa %r" % (PARTNER_MARKER,))
    return 0


def main() -> int:
    return run(CONFIG)


if __name__ == "__main__":
    raise SystemExit(main())
