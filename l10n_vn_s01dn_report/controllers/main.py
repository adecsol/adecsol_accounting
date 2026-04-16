# -*- coding: utf-8 -*-
"""
Sau khi merge `options` (wizard + filter), `context` có thể là dict (JSON lồng).
Cả report_xlsx lẫn web.report đều gọi json.loads(data['context']) — cần chuỗi JSON.

Tên file XLSX: report_xlsx chỉ eval `print_report_name` khi URL có docids.
Client luôn gọi /report/xlsx/<name>?options=... khi action có `data` (wizard + nút Excel trên HTML),
nên cần đặt Content-Disposition từ date trong options (khớp report.xml).
"""

import json
from datetime import datetime

from werkzeug.urls import url_decode

from odoo.addons.report_xlsx.controllers.main import ReportController as ReportXlsxController
from odoo.http import content_disposition, route

S01DN_XLSX_REPORT = "l10n_vn_s01dn_report.general_ledger_s01dn_xlsx"


def _s01dn_xlsx_download_filename_from_url(url):
    """Khớp print_report_name trong report.xml khi thiếu docids trên URL."""
    if S01DN_XLSX_REPORT not in url or "?" not in url:
        return None
    try:
        query = url.split("?", 1)[1]
        params = dict(url_decode(query).items())
        raw_opts = params.get("options")
        if not raw_opts:
            return None
        opts = json.loads(raw_opts)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None

    ui = opts.get("s01dn_ui_filters") or {}
    if not isinstance(ui, dict):
        ui = {}

    def _pick(*vals):
        for v in vals:
            if v is None or v is False:
                continue
            if isinstance(v, str) and not v.strip():
                continue
            return v
        return None

    df_raw = _pick(ui.get("date_from"), opts.get("date_from"))
    dt_raw = _pick(ui.get("date_to"), opts.get("date_to"))
    if df_raw is None or dt_raw is None:
        return None

    try:
        if isinstance(df_raw, str):
            df = datetime.strptime(df_raw.strip()[:10], "%Y-%m-%d").date()
        else:
            df = datetime.strptime(str(df_raw)[:10], "%Y-%m-%d").date()
        if isinstance(dt_raw, str):
            dt = datetime.strptime(dt_raw.strip()[:10], "%Y-%m-%d").date()
        else:
            dt = datetime.strptime(str(dt_raw)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None

    return (
        f"Journal_Ledger_S01_DN_{df.strftime('%d%m%Y')}_{dt.strftime('%d%m%Y')}.xlsx"
    )


class ReportController(ReportXlsxController):
    @route()
    def report_routes(self, reportname, docids=None, converter=None, **data):
        data = dict(data)
        if data.get("options"):
            data.update(json.loads(data.pop("options")))
        if data.get("context") is not None and isinstance(data["context"], dict):
            data["context"] = json.dumps(data["context"])
        return super().report_routes(
            reportname, docids=docids, converter=converter, **data,
        )

    @route()
    def report_download(self, data, context=None, token=None, readonly=True):
        requestcontent = json.loads(data)
        url = requestcontent[0]
        report_type = requestcontent[1]
        filename_override = None
        if report_type == "xlsx":
            filename_override = _s01dn_xlsx_download_filename_from_url(url)

        response = super().report_download(
            data, context=context, token=token, readonly=readonly,
        )

        if not filename_override or response is None:
            return response

        ctype = (response.headers.get("Content-Type") or "").lower()
        if "spreadsheetml" not in ctype:
            return response

        response.headers["Content-Disposition"] = content_disposition(
            filename_override
        )
        return response
