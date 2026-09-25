import sqlite3
import pandas as pd

SILVER_DB = "lakehouse/silver.db"
GOLD_DB = "lakehouse/gold.db"

def build_gold_layer():
    print("🥇 [Gold Layer] กำลังคำนวณโมเดลข้อมูลระดับธุรกิจ (Star Schema)...")
    
    # ดึงตารางจากระดับ Silver
    conn_src = sqlite3.connect(SILVER_DB)
    orders = pd.read_sql("SELECT * FROM stg_orders", conn_src)
    details = pd.read_sql("SELECT * FROM stg_order_details", conn_src)
    products = pd.read_sql("SELECT * FROM stg_products", conn_src)
    shippers = pd.read_sql("SELECT * FROM stg_shippers", conn_src)
    conn_src.close()
    
    # เชื่อมต่อระบบฐานข้อมูล Gold
    conn_dest = sqlite3.connect(GOLD_DB)
    
    # --- 1. สร้างตารางมิติ: dim_products & dim_shippers ---
    products.to_sql("dim_products", conn_dest, if_exists="replace", index=False)
    shippers.to_sql("dim_shippers", conn_dest, if_exists="replace", index=False)
    print(" ✔ โหลดตารางมิติสินค้าและผู้ขนส่งเรียบร้อย")

    # --- 2. สร้างตารางมิติเวลา: dim_date (เพื่อตอบโจทย์วิเคราะห์ รายวัน/รายสัปดาห์) ---
    all_dates = pd.to_datetime(orders["OrderDate"].unique())
    dim_date = pd.DataFrame({
        "DateKey": all_dates.strftime('%Y%m%d').astype(int),
        "FullDate": all_dates.strftime('%Y-%m-%d'),
        "Year": all_dates.year,
        "Month": all_dates.month,
        "MonthName": all_dates.strftime('%B'),
        "WeekOfYear": all_dates.isocalendar().week,
        "DayOfWeek": all_dates.isocalendar().day,
        "DayName": all_dates.strftime('%A')
    })
    dim_date.to_sql("dim_date", conn_dest, if_exists="replace", index=False)
    print(" ✔ ปั้นมิติด้านกาลเวลา (dim_date) เรียบร้อย")

    # --- 3. สร้างตารางข้อเท็จจริงหลัก: fact_sales_velocity ---
    # รวมบิล (Orders) และรายละเอียดสินค้า (Details) เข้าด้วยกัน
    fact_sales = pd.merge(details, orders, on="OrderID", how="inner")
    
    # แปลงคอลัมน์วันให้อยู่ในรูป DateKey เพื่อเชื่อมความสัมพันธ์
    fact_sales["OrderDateKey"] = pd.to_datetime(fact_sales["OrderDate"]).dt.strftime('%Y%m%d').astype(int)
    
    # เลือกเฉพาะคอลัมน์ที่จำเป็นสำหรับ Fact Table
    fact_cols = ["OrderID", "CustomerID", "ProductID", "ShipperID", "OrderDateKey", "Quantity", "UnitPrice", "Discount", "Freight"]
    fact_sales_final = fact_sales[fact_cols]
    
    fact_sales_final.to_sql("fact_sales_velocity", conn_dest, if_exists="replace", index=False)
    print(" ✔ ประกอบตารางข้อเท็จจริงหลัก (fact_sales_velocity) เรียบร้อย")
    
    # --- 4. ทดสอบ Query คำตอบทางธุรกิจ ---
    print("\n📊 --- [ผลการวิเคราะห์ตัวอย่างความถี่คำสั่งซื้อรายสัปดาห์ในชั้น Gold] ---")
    query = """
    SELECT 
        d.Year, 
        d.WeekOfYear, 
        COUNT(DISTINCT f.OrderID) AS Total_Bills,
        SUM(f.Quantity) AS Total_Items_Sold
    FROM fact_sales_velocity f
    JOIN dim_date d ON f.OrderDateKey = d.DateKey
    GROUP BY d.Year, d.WeekOfYear
    LIMIT 5;
    """
    res = pd.read_sql(query, conn_dest)
    print(res.to_string(index=False))
    
    conn_dest.close()

if __name__ == "__main__":
    build_gold_layer()
    print("\n🎉 สถาปัตยกรรมคลังข้อมูลแบบ Medallion Pattern รันครบถ้วนสมบูรณ์แล้ว!")
