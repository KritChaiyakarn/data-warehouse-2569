import os
import json
import sqlite3
import pandas as pd
from docx import Document

BRONZE_DIR = "lakehouse/bronze"
SILVER_DB = "lakehouse/silver.db"

def build_silver_layer():
    print("🥈 [Silver Layer] กำลังแปลงข้อมูลดิบและทำความสะอาด...")
    os.makedirs("lakehouse", exist_ok=True)
    conn = sqlite3.connect(SILVER_DB)
    
    # 1. จัดการตารางคำสั่งซื้อ (Orders) จาก Excel
    df_orders = pd.read_excel(os.path.join(BRONZE_DIR, "orders/orders_2026.xlsx"))
    df_orders["OrderDate"] = pd.to_datetime(df_orders["OrderDate"]).dt.strftime('%Y-%m-%d')
    df_orders.to_sql("stg_orders", conn, if_exists="replace", index=False)
    print(" ✔ ทำความสะอาดและโหลดตาราง 'stg_orders' แล้ว")

    # 2. จัดการตารางรายละเอียด (Order Details) จาก Text/Pipe Delimiter
    df_details = pd.read_csv(os.path.join(BRONZE_DIR, "order_details/order_details.txt"), sep="|")
    df_details.to_sql("stg_order_details", conn, if_exists="replace", index=False)
    print(" ✔ ทำความสะอาดและโหลดตาราง 'stg_order_details' แล้ว")

    # 3. จัดการตารางสินค้า (Products) จาก JSON (ทำการ Flatten ชิ้นข้อมูล)
    with open(os.path.join(BRONZE_DIR, "products/products.json"), "r", encoding="utf-8") as f:
        products_raw = json.load(f)
    
    flattened_products = []
    for p in products_raw:
        flattened_products.append({
            "ProductID": p["ProductID"],
            "ProductName": p["ProductName"],
            "CategoryID": p["CategoryID"],
            "QuantityPerUnit": p["Specs"]["QuantityPerUnit"],
            "UnitPrice": p["Specs"]["UnitPrice"]
        })
    pd.DataFrame(flattened_products).to_sql("stg_products", conn, if_exists="replace", index=False)
    print(" ✔ คลี่ข้อมูลหลากมิติและโหลดตาราง 'stg_products' แล้ว")

    # 4. แปลงข้อมูลไม่มีโครงสร้าง (DOCX) มาสกัดโครงสร้างบริษัทยนส่ง (Shippers)
    doc = Document(os.path.join(BRONZE_DIR, "shippers_policy/shippers_policy.docx"))
    shippers_extracted = []
    
    # สแกนหาบรรทัดที่มีข้อความรหัสผู้จัดส่ง (SHIP_ID)
    for p in doc.paragraphs:
        if "SHIP_ID:" in p.text:
            # ตัวอย่างบรรทัด: "• SHIP_ID: 1 -> ไปรษณีย์ไทย (Thailand Post)"
            parts = p.text.split("->")
            ship_id = int(parts[0].replace("• SHIP_ID:", "").strip())
            ship_name = parts[1].strip()
            shippers_extracted.append({"ShipperID": ship_id, "ShipperName": ship_name})
            
    pd.DataFrame(shippers_extracted).to_sql("stg_shippers", conn, if_exists="replace", index=False)
    print(" ✔ สกัดข้อมูล Unstructured Text และโหลดตาราง 'stg_shippers' แล้ว")

    conn.close()

if __name__ == "__main__":
    build_silver_layer()
    print("🎉 ล้างข้อมูลและสร้างชั้น Silver สำเร็จ!\n")
