"""
Synthetic Retail Data Generator for Sales & Inventory Copilot (PS03)
Generates:
  - data/stores.csv
  - data/products.csv
  - data/inventory.csv
  - data/sales.csv
Includes calibrated scenarios for:
  - Low stock (imminent stock-out)
  - Overstocked items
  - Slow-moving stock
  - Sales spikes
  - Sales drops
  - Normal steady movement
"""
import os
import csv
import random
from datetime import datetime, timedelta

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

STORES = [
    {
        "store_id": "ST01",
        "store_name": "Koramangala Flagship Superstore",
        "location": "80 Feet Rd, Koramangala 4th Block, Bengaluru"
    },
    {
        "store_id": "ST02",
        "store_name": "Indiranagar Metro Express",
        "location": "100 Feet Rd, HAL 2nd Stage, Indiranagar, Bengaluru"
    },
    {
        "store_id": "ST03",
        "store_name": "Jayanagar Mega Mart",
        "location": "11th Main Rd, 4th Block, Jayanagar, Bengaluru"
    }
]

PRODUCTS = [
    # Groceries & Staples
    {
        "product_id": "PRD001",
        "product_name": "Tata Tea Gold 500g",
        "category": "Groceries & Staples",
        "price": 310.00,
        "supplier": "Tata Consumer Products",
        "scenario": "low_stock"  # Fast-selling, low inventory left
    },
    {
        "product_id": "PRD002",
        "product_name": "Aashirvaad Shudh Chakki Atta 5kg",
        "category": "Groceries & Staples",
        "price": 245.00,
        "supplier": "ITC Limited",
        "scenario": "normal"
    },
    {
        "product_id": "PRD003",
        "product_name": "Fortune Sunlite Sunflower Oil 1L",
        "category": "Groceries & Staples",
        "price": 135.00,
        "supplier": "Adani Wilmar",
        "scenario": "sales_drop"  # Recent sharp drop in demand
    },
    {
        "product_id": "PRD004",
        "product_name": "Tata Salt Vacuum Evaporated 1kg",
        "category": "Groceries & Staples",
        "price": 28.00,
        "supplier": "Tata Consumer Products",
        "scenario": "normal"
    },
    {
        "product_id": "PRD005",
        "product_name": "India Gate Basmati Rice Feast Rozzana 1kg",
        "category": "Groceries & Staples",
        "price": 115.00,
        "supplier": "KRBL Limited",
        "scenario": "normal"
    },

    # Snacks & Beverages
    {
        "product_id": "PRD006",
        "product_name": "Maggi 2-Minute Masala Noodles 70g",
        "category": "Snacks & Beverages",
        "price": 14.00,
        "supplier": "Nestle India",
        "scenario": "normal"
    },
    {
        "product_id": "PRD007",
        "product_name": "Haldiram's Nagpur Bhujia 400g",
        "category": "Snacks & Beverages",
        "price": 120.00,
        "supplier": "Haldiram Foods",
        "scenario": "normal"
    },
    {
        "product_id": "PRD008",
        "product_name": "Cadbury Dairy Milk Silk 150g",
        "category": "Snacks & Beverages",
        "price": 175.00,
        "supplier": "Mondelez India",
        "scenario": "overstock"  # Huge stock relative to sales
    },
    {
        "product_id": "PRD009",
        "product_name": "Red Bull Energy Drink 250ml",
        "category": "Snacks & Beverages",
        "price": 125.00,
        "supplier": "Red Bull India",
        "scenario": "sales_spike"  # Weekend / event surge
    },
    {
        "product_id": "PRD010",
        "product_name": "Amul Butter Pasteurised 500g",
        "category": "Dairy & Chilled",
        "price": 275.00,
        "supplier": "Gujarat Co-op Milk Marketing",
        "scenario": "normal"
    },

    # Personal Care
    {
        "product_id": "PRD011",
        "product_name": "Dettol Liquid Handwash Refill 750ml",
        "category": "Personal Care",
        "price": 109.00,
        "supplier": "Reckitt Benckiser",
        "scenario": "sales_drop"  # Recent sharp decline
    },
    {
        "product_id": "PRD012",
        "product_name": "Colgate MaxFresh Peppermint 150g",
        "category": "Personal Care",
        "price": 110.00,
        "supplier": "Colgate-Palmolive",
        "scenario": "normal"
    },
    {
        "product_id": "PRD013",
        "product_name": "Dove Intense Repair Shampoo 340ml",
        "category": "Personal Care",
        "price": 299.00,
        "supplier": "Hindustan Unilever",
        "scenario": "normal"
    },
    {
        "product_id": "PRD014",
        "product_name": "Nivea Soft Light Moisturizing Cream 200ml",
        "category": "Personal Care",
        "price": 320.00,
        "supplier": "Nivea India",
        "scenario": "slow_moving"  # Barely selling, high sitting stock
    },

    # Electronics & Accessories
    {
        "product_id": "PRD015",
        "product_name": "boAt Rockerz 255 Pro+ Wireless Neckband",
        "category": "Electronics & Accessories",
        "price": 999.00,
        "supplier": "Imagine Marketing (boAt)",
        "scenario": "sales_spike"  # Viral demand spike
    },
    {
        "product_id": "PRD016",
        "product_name": "Portronics Konnect Pro Type-C Cable 1m",
        "category": "Electronics & Accessories",
        "price": 199.00,
        "supplier": "Portronics Digital",
        "scenario": "low_stock"  # Imminent stockout
    },
    {
        "product_id": "PRD017",
        "product_name": "Mi 10000mAh Power Bank 3i",
        "category": "Electronics & Accessories",
        "price": 1299.00,
        "supplier": "Xiaomi India",
        "scenario": "normal"
    },

    # Home & Kitchen
    {
        "product_id": "PRD018",
        "product_name": "Surf Excel Matic Front Load Liquid Detergent 2L",
        "category": "Home & Kitchen",
        "price": 460.00,
        "supplier": "Hindustan Unilever",
        "scenario": "normal"
    },
    {
        "product_id": "PRD019",
        "product_name": "Prestige Popular Aluminium Pressure Cooker 3L",
        "category": "Home & Kitchen",
        "price": 1450.00,
        "supplier": "TTK Prestige",
        "scenario": "overstock"  # Heavy overstock across stores
    },
    {
        "product_id": "PRD020",
        "product_name": "Havells 4-Socket Surge Protector Extension Board",
        "category": "Home & Kitchen",
        "price": 599.00,
        "supplier": "Havells India",
        "scenario": "slow_moving"  # Zero/negligible recent sales
    }
]

def generate_csv_data():
    os.makedirs(DATA_DIR, exist_ok=True)
    random.seed(42)  # Deterministic generation

    # 1. Write Stores
    stores_path = os.path.join(DATA_DIR, "stores.csv")
    with open(stores_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["store_id", "store_name", "location"])
        writer.writeheader()
        writer.writerows(STORES)

    # 2. Write Products
    products_path = os.path.join(DATA_DIR, "products.csv")
    clean_products = []
    for p in PRODUCTS:
        clean_products.append({
            "product_id": p["product_id"],
            "product_name": p["product_name"],
            "category": p["category"],
            "price": f"{p['price']:.2f}",
            "supplier": p["supplier"]
        })
    with open(products_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["product_id", "product_name", "category", "price", "supplier"])
        writer.writeheader()
        writer.writerows(clean_products)

    # 3. Generate Sales (45 days up to 2026-09-04)
    end_date = datetime(2026, 9, 4)
    start_date = end_date - timedelta(days=44)  # 45 days total

    sales_rows = []
    current_date = start_date

    # Store baseline sales quantity per day per store
    while current_date <= end_date:
        days_from_end = (end_date - current_date).days
        is_weekend = current_date.weekday() in (5, 6)
        date_str = current_date.strftime("%Y-%m-%d")

        for p in PRODUCTS:
            pid = p["product_id"]
            price = p["price"]
            scenario = p["scenario"]

            for s in STORES:
                sid = s["store_id"]

                # Determine daily quantity based on calibrated scenario
                qty = 0
                if scenario == "normal":
                    base = 4 if "Groceries" in p["category"] or "Snacks" in p["category"] else 2
                    qty = base + random.randint(0, 3)
                    if is_weekend:
                        qty += random.randint(1, 2)

                elif scenario == "low_stock":
                    # Consistently high demand, but inventory not replenished
                    base = 4 if sid == "ST01" else 3
                    qty = base + random.randint(0, 2)
                    if is_weekend:
                        qty += 2

                elif scenario == "overstock":
                    # Slow, steady or minimal sales
                    qty = 1 if random.random() < 0.4 else 0
                    if is_weekend and random.random() < 0.6:
                        qty = 1

                elif scenario == "slow_moving":
                    # Almost dead stock: only 1 or 2 sales in past 45 days
                    if days_from_end > 30 and random.random() < 0.08:
                        qty = 1
                    else:
                        qty = 0

                elif scenario == "sales_spike":
                    # In last 7 days, sales jump dramatically
                    if days_from_end <= 7:
                        # Massive surge
                        qty = random.randint(8, 14) if sid == "ST01" else random.randint(6, 10)
                    else:
                        # Historical low/moderate baseline
                        qty = random.randint(1, 3)

                elif scenario == "sales_drop":
                    # In last 7 days, sales drop to near zero or 1
                    if days_from_end <= 7:
                        qty = 1 if random.random() < 0.3 else 0
                    else:
                        # Historical steady sales
                        qty = random.randint(5, 8) if is_weekend else random.randint(4, 7)

                revenue = round(qty * price, 2)
                sales_rows.append({
                    "date": date_str,
                    "store_id": sid,
                    "product_id": pid,
                    "quantity_sold": qty,
                    "revenue": f"{revenue:.2f}"
                })

        current_date += timedelta(days=1)

    sales_path = os.path.join(DATA_DIR, "sales.csv")
    with open(sales_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "store_id", "product_id", "quantity_sold", "revenue"])
        writer.writeheader()
        writer.writerows(sales_rows)

    # 4. Generate Current Inventory (as of 2026-09-04)
    inventory_rows = []
    inv_date_str = end_date.strftime("%Y-%m-%d")

    for p in PRODUCTS:
        pid = p["product_id"]
        scenario = p["scenario"]

        for s in STORES:
            sid = s["store_id"]
            stock = 50  # default

            if scenario == "low_stock":
                # Only 4 to 8 units in stock (less than 2-3 days of stock!)
                stock = random.randint(4, 8) if sid == "ST01" else random.randint(7, 12)

            elif scenario == "overstock":
                # 150 to 300 units in stock!
                stock = random.randint(140, 220) if sid == "ST03" else random.randint(110, 180)

            elif scenario == "slow_moving":
                # High sitting inventory that doesn't sell
                stock = random.randint(45, 85)

            elif scenario == "sales_spike":
                # Rapidly depleting due to recent spike
                stock = random.randint(25, 40)

            elif scenario == "sales_drop":
                # Moderate stock piling up because sales stopped
                stock = random.randint(60, 90)

            elif scenario == "normal":
                stock = random.randint(35, 75)

            inventory_rows.append({
                "date": inv_date_str,
                "store_id": sid,
                "product_id": pid,
                "stock_quantity": stock
            })

    inventory_path = os.path.join(DATA_DIR, "inventory.csv")
    with open(inventory_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "store_id", "product_id", "stock_quantity"])
        writer.writeheader()
        writer.writerows(inventory_rows)

    print(f"Successfully generated synthetic dataset:")
    print(f"  Stores: {len(STORES)} records -> {stores_path}")
    print(f"  Products: {len(PRODUCTS)} records -> {products_path}")
    print(f"  Sales: {len(sales_rows)} daily records -> {sales_path}")
    print(f"  Inventory: {len(inventory_rows)} records -> {inventory_path}")

if __name__ == "__main__":
    generate_csv_data()
