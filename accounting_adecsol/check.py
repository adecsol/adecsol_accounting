import psycopg2
import json

def check_odoo18_coa():
    """Kiểm tra COA trong Odoo 18"""
    
    conn = psycopg2.connect(
        host="localhost",
        port="5435",
        database="odoo_UU",
        user="odoo",
        password="gAnmGAQN"
    )
    
    cur = conn.cursor()
    
    print("=" * 80)
    print("KIỂM TRA HỆ THỐNG KẾ TOÁN ODOO 18")
    print("=" * 80)
    
    # 1. Kiểm tra Account Groups
    print("\n1. ACCOUNT GROUPS (Nhóm tài khoản):")
    print("-" * 50)
    
    cur.execute("""
        SELECT 
            ag.name,
            ag.code_prefix_start,
            ag.code_prefix_end,
            COUNT(aa.id) as account_count
        FROM account_group ag
        LEFT JOIN account_account aa ON ag.id = aa.group_id AND aa.company_id = 2
        WHERE ag.company_id = 2
        GROUP BY ag.id, ag.name, ag.code_prefix_start, ag.code_prefix_end
        ORDER BY ag.code_prefix_start
    """)
    
    groups = cur.fetchall()
    print(f"Tổng số Groups: {len(groups)}")
    
    # Phân tích theo TT200
    categories = {
        '1': {'name': 'Tài sản ngắn hạn', 'count': 0, 'groups': []},
        '2': {'name': 'Tài sản dài hạn', 'count': 0, 'groups': []},
        '3': {'name': 'Nợ phải trả', 'count': 0, 'groups': []},
        '4': {'name': 'Vốn chủ sở hữu', 'count': 0, 'groups': []},
        '5': {'name': 'Doanh thu', 'count': 0, 'groups': []},
        '6': {'name': 'Chi phí SXKD', 'count': 0, 'groups': []},
        '7': {'name': 'Thu nhập khác', 'count': 0, 'groups': []},
        '8': {'name': 'Chi phí khác', 'count': 0, 'groups': []},
        '9': {'name': 'Xác định KQKD', 'count': 0, 'groups': []}
    }
    
    for name, start, end, acc_count in groups[:15]:  # Hiển thị 15 cái đầu
        if start and len(start) > 0:
            category = start[0]
            if category in categories:
                categories[category]['count'] += 1
                categories[category]['groups'].append(f"{start}-{end}: {name}")
            
            print(f"  {start}-{end}: {name} ({acc_count} tài khoản)")
    
    # 2. Phân tích theo TT200
    print("\n2. PHÂN TÍCH THEO THÔNG TƯ 200:")
    print("-" * 50)
    
    for cat_num, cat_info in sorted(categories.items()):
        if cat_info['count'] > 0:
            print(f"\n{cat_num}. {cat_info['name']}: {cat_info['count']} groups")
            for group_info in cat_info['groups'][:3]:  # Hiển thị 3 groups đầu
                print(f"   - {group_info}")
            if len(cat_info['groups']) > 3:
                print(f"   ... và {len(cat_info['groups']) - 3} groups khác")
    
    # 3. Kiểm tra tài khoản
    print("\n3. TÀI KHOẢN CHI TIẾT:")
    print("-" * 50)
    
    cur.execute("""
        SELECT COUNT(*) as total_accounts
        FROM account_account 
        WHERE company_id = 2
    """)
    
    total_accounts = cur.fetchone()[0]
    print(f"Tổng số tài khoản: {total_accounts}")
    
    if total_accounts > 0:
        # Lấy mẫu tài khoản
        cur.execute("""
            SELECT 
                aa.name->>'vi_VN' as name_vn,
                aa.account_type,
                ag.name as group_name,
                ag.code_prefix_start
            FROM account_account aa
            LEFT JOIN account_group ag ON aa.group_id = ag.id
            WHERE aa.company_id = 2
            ORDER BY ag.code_prefix_start, aa.name->>'vi_VN'
            LIMIT 15
        """)
        
        accounts = cur.fetchall()
        print("\nMẫu tài khoản (15 cái đầu):")
        for name_vn, acc_type, group_name, prefix in accounts:
            display_name = name_vn if name_vn else "Không có tên tiếng Việt"
            print(f"  {prefix}xxx: {display_name} [{group_name}] - Loại: {acc_type}")
    
    # 4. Kiểm tra các tài khoản quan trọng theo TT200
    print("\n4. KIỂM TRA TÀI KHOẢN QUAN TRỌNG:")
    print("-" * 50)
    
    # Các mã tài khoản bắt buộc
    mandatory_codes = [
        ('111', 'Tiền mặt'),
        ('112', 'Tiền gửi ngân hàng'),
        ('131', 'Phải thu khách hàng'),
        ('331', 'Phải trả người bán'),
        ('411', 'Vốn chủ sở hữu'),
        ('511', 'Doanh thu bán hàng'),
        ('632', 'Giá vốn hàng bán'),
        ('911', 'Xác định kết quả kinh doanh')
    ]
    
    for code, expected_name in mandatory_codes:
        cur.execute("""
            SELECT ag.name, COUNT(aa.id)
            FROM account_group ag
            LEFT JOIN account_account aa ON ag.id = aa.group_id AND aa.company_id = 2
            WHERE ag.company_id = 2 
            AND ag.code_prefix_start <= %s 
            AND ag.code_prefix_end >= %s
            GROUP BY ag.name
        """, (code, code))
        
        result = cur.fetchone()
        if result:
            group_name, account_count = result
            status = "✓" if account_count > 0 else "⚠"
            print(f"  {status} {code}: {expected_name}")
            print(f"     Nhóm: {group_name} ({account_count} tài khoản)")
        else:
            print(f"  ✗ {code}: {expected_name} (THIẾU NHÓM)")
    
    # 5. Tổng kết
    print("\n" + "=" * 80)
    print("TỔNG KẾT:")
    print("=" * 80)
    
    # Tính tổng số groups theo TT200
    total_tt200_groups = sum(cat['count'] for cat in categories.values())
    print(f"1. Tổng số Account Groups: {len(groups)}")
    print(f"2. Phân bổ theo TT200: {total_tt200_groups}/9 loại đầy đủ")
    
    # Kiểm tra xem có đủ 9 loại không
    missing_categories = []
    for cat_num, cat_info in categories.items():
        if cat_info['count'] == 0:
            missing_categories.append(cat_num)
    
    if missing_categories:
        print(f"3. THIẾU loại tài khoản: {', '.join(missing_categories)}")
    else:
        print("3. ✓ ĐẦY ĐỦ 9 loại tài khoản theo TT200")
    
    print(f"4. Tổng số tài khoản chi tiết: {total_accounts}")
    
    if total_accounts == 0:
        print("5. ⚠ CHƯA CÓ TÀI KHOẢN CHI TIẾT")
        print("   Cần import danh mục tài khoản vào các groups")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_odoo18_coa()