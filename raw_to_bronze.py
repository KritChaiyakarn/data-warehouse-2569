import os
import shutil

# กำหนดเส้นทางโฟลเดอร์
RAW_DIR = "northwind_thai_large_data"
BRONZE_DIR = "lakehouse/bronze"

def ingest_to_bronze():
    print("🥉 [Bronze Layer] กำลังคัดลอกข้อมูลดิบเข้าสู่ Raw Zone...")
    
    # สร้างโครงสร้างโฟลเดอร์แยกตาม Source แต่ละตัว
    files_to_move = {
        "customers.csv": "customers/customers.csv",
        "products.json": "products/products.json",
        "orders_2026.xlsx": "orders/orders_2026.xlsx",
        "order_details.txt": "order_details/order_details.txt",
        "shippers_policy.docx": "shippers_policy/shippers_policy.docx"
    }
    
    for src_file, dest_path in files_to_move.items():
        src = os.path.join(RAW_DIR, src_file)
        dest = os.path.join(BRONZE_DIR, dest_path)
        
        if os.path.exists(src):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy(src, dest)
            print(f" ✔ ย้ายข้อมูล {src_file} -> {dest}")
        else:
            print(f" ❌ ไม่พบไฟล์ต้นทาง: {src}")

if __name__ == "__main__":
    ingest_to_bronze()
    print("🎉 ย้ายข้อมูลเข้าสู่ชั้น Bronze เรียบร้อย!\n")
