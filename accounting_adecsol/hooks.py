# -*- coding: utf-8 -*-
import json
from odoo import api


def pre_init_hook(env):
    """ Bước 1: Xóa sạch tuyệt đối dữ liệu cũ """
    cr = env.cr
    cr.execute("UPDATE account_journal SET default_account_id = NULL, suspense_account_id = NULL;")
    cr.execute("DELETE FROM account_move_line CASCADE;")
    cr.execute("DELETE FROM account_move CASCADE;")
    cr.execute("DELETE FROM account_account CASCADE;")
    cr.execute("DELETE FROM account_group CASCADE;")


def post_init_hook(env):
    """
    Bước 2: Ép COA theo TT200 + TT99 cho Công ty An Dương (ID = 2)

    ⚠ Odoo 18 NOTE:
    - account.account KHÔNG CÒN group_id / account_group_id
    - Account Group được xác định LOGIC bằng code_prefix
    - TUYỆT ĐỐI không update group vào account
    """
    cr = env.cr
    TARGET_CO_ID = 2

    # =====================================================
    # 1. Tạo Account Group (chỉ cần prefix)
    # =====================================================
    group_data = {
        '11': 'Tiền và các khoản tương đương tiền',
        '12': 'Đầu tư tài chính',
        '13': 'Phải thu khách hàng',
        '15': 'Hàng tồn kho',
        '21': 'Tài sản cố định',
        '33': 'Nợ phải trả',
        '41': 'Vốn chủ sở hữu',
        '51': 'Doanh thu bán hàng và cung cấp dịch vụ',
        '64': 'Chi phí quản lý kinh doanh',
    }

    for g_code, g_name in group_data.items():
        env['account.group'].sudo().create({
            'name': f"{g_code} - {g_name}",
            'code_prefix_start': g_code,
            'code_prefix_end': g_code,
            'company_id': TARGET_CO_ID,
        })

    # =====================================================
    # 2. Chuẩn hóa Account (KHÔNG gán group)
    # =====================================================
    accounts = env['account.account'].sudo().search([])

    for acc in accounts:
        raw_code = acc.code or ""

        # TT200: 1110 -> 111
        code = raw_code
        if len(code) == 4 and code.endswith('0'):
            code = code[:3]

        # Fix multi-company: chỉ thuộc company 2
        cr.execute(
            "DELETE FROM account_account_res_company_rel WHERE account_account_id = %s",
            (acc.id,)
        )
        cr.execute(
            """
            INSERT INTO account_account_res_company_rel
            (account_account_id, res_company_id)
            VALUES (%s, %s)
            """,
            (acc.id, TARGET_CO_ID)
        )

        # Odoo 18: code_store BẮT BUỘC
        code_store_json = json.dumps({
            str(TARGET_CO_ID): [code, acc.account_type]
        })

        cr.execute(
            """
            UPDATE account_account
            SET code_store = %s
            WHERE id = %s
            """,
            (code_store_json, acc.id)
        )

    env.registry.clear_cache()
    print(">>> HOOK OK: COA TT200 + TT99 – đúng kiến trúc Odoo 18")
