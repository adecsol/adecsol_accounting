import psycopg2
import sys

def check_coa_compliance():
    # Kết nối database
    conn = psycopg2.connect(
        host="localhost",
        port="5435",
        database="odoo_UU",
        user="odoo",
        password="gAnmGAQN"
    )
    
    cur = conn.cursor()
    
    print("=" * 80)
    print("KIỂM TRA COA THEO TT200 & TT99")
    print("=" * 80)
    
    # 1. Lấy danh sách tài khoản
    cur.execute("""
        SELECT code, name, account_type 
        FROM account_account 
        WHERE company_id = 2 
        ORDER BY code
    """)
    
    accounts = cur.fetchall()
    
    print(f"\nTổng số tài khoản: {len(accounts)}")
    
    # 2. Kiểm tra TT200
    print("\n" + "=" * 80)
    print("KIỂM TRA THÔNG TƯ 200/2014/TT-BTC")
    print("=" * 80)
    
    tt200_violations = []
    category_counts = {str(i): 0 for i in range(1, 10)}
    
    for code, name, account_type in accounts:
        # Kiểm tra độ dài
        if not (3 <= len(code) <= 6):
            tt200_violations.append(f"{code} - {name}: Độ dài {len(code)} không hợp lệ (3-6)")
        
        # Kiểm tra chữ số đầu
        if not code[0].isdigit() or code[0] == '0':
            tt200_violations.append(f"{code} - {name}: Chữ số đầu '{code[0]}' không hợp lệ")
        else:
            category_counts[code[0]] = category_counts.get(code[0], 0) + 1
        
        # Kiểm tra toàn bộ là số
        if not code.isdigit():
            tt200_violations.append(f"{code} - {name}: Chứa ký tự không phải số")
    
    # 3. Kiểm tra TT99
    print("\n" + "=" * 80)
    print("KIỂM TRA THÔNG TƯ 99/2024/TT-BTC")
    print("=" * 80)
    
    # Tài khoản mới theo TT99
    tt99_new_accounts = ['116', '117', '356', '6357', '736', '8118']
    tt99_found = []
    
    for code, name, account_type in accounts:
        if any(code.startswith(prefix) for prefix in ['116', '117', '356']):
            tt99_found.append(f"{code} - {name}: Tài khoản phái sinh (TT99)")
    
    # 4. In kết quả
    print("\nPHÂN BỔ THEO LOẠI TÀI KHOẢN:")
    for category, count in sorted(category_counts.items()):
        category_names = {
            '1': '1 - Tài sản ngắn hạn',
            '2': '2 - Tài sản dài hạn',
            '3': '3 - Nợ phải trả',
            '4': '4 - Vốn chủ sở hữu',
            '5': '5 - Doanh thu',
            '6': '6 - Chi phí SXKD',
            '7': '7 - Thu nhập khác',
            '8': '8 - Chi phí khác',
            '9': '9 - Xác định KQKD'
        }
        if count > 0:
            print(f"  {category_names.get(category, category)}: {count} tài khoản")
    
    print("\nTÀI KHOẢN THEO TT99:")
    if tt99_found:
        for account in tt99_found:
            print(f"  ✓ {account}")
    else:
        print("  Không có tài khoản đặc thù TT99")
    
    print("\nVI PHẠM TT200:")
    if tt200_violations:
        for violation in tt200_violations[:10]:  # Hiển thị 10 lỗi đầu
            print(f"  ✗ {violation}")
        if len(tt200_violations) > 10:
            print(f"  ... và {len(tt200_violations) - 10} lỗi khác")
    else:
        print("  ✓ Không có vi phạm")
    
    # 5. Kiểm tra tài khoản bắt buộc
    print("\nTÀI KHOẢN BẮT BUỘC:")
    mandatory_accounts = [
        ('111', 'Tiền mặt'),
        ('112', 'Tiền gửi ngân hàng'),
        ('131', 'Phải thu khách hàng'),
        ('331', 'Phải trả người bán'),
        ('411', 'Vốn đầu tư của chủ sở hữu'),
        ('511', 'Doanh thu bán hàng'),
        ('632', 'Giá vốn hàng bán'),
        ('911', 'Xác định kết quả kinh doanh')
    ]
    
    for code, name in mandatory_accounts:
        cur.execute(
            "SELECT 1 FROM account_account WHERE code = %s AND company_id = 2",
            (code,)
        )
        if cur.fetchone():
            print(f"  ✓ {code} - {name}")
        else:
            print(f"  ✗ {code} - {name} (THIẾU)")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 80)
    print("KẾT LUẬN:")
    if not tt200_violations:
        print("✓ COA TUÂN THỦ TT200")
    else:
        print("✗ COA CÓ VI PHẠM TT200")
    
    print("=" * 80)

if __name__ == "__main__":
    check_coa_compliance()