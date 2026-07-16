import random
import time
from sqlalchemy import insert
from app.database.session import SessionLocal
from app.models.domain import User, Product, Cart, CartItem

def seed_massive_data():
    db = SessionLocal()
    try:
        print("Starting Enterprise Data Generation (5 Million Rows)...")
        start_time = time.time()

        # 1. Seed 100,000 Users
        print("Seeding 100,000 Users...")
        user_data = [
            {"email": f"user{i}@cart.com", "name": f"User {i}"} 
            for i in range(1, 100001)
        ]
        db.execute(insert(User), user_data)
        db.commit()

        # 2. Seed 10,000 Products
        print("Seeding 10,000 Products...")
        product_data = [
            {
                "name": f"Enterprise Product {i}", 
                "price": round(random.uniform(10.0, 5000.0), 2), 
                "stock": random.randint(10, 1000), 
                "reserved_stock": 0
            } 
            for i in range(1, 10001)
        ]
        db.execute(insert(Product), product_data)
        db.commit()

        # 3. Seed 1,000,000 Carts (Chunked to save RAM)
        print("Seeding 1,000,000 Carts (in chunks of 100,000)...")
        cart_statuses = ["active", "checked_out", "abandoned"]
        
        for chunk in range(10): 
            cart_data = [
                {
                    "user_id": random.randint(1, 100000), 
                    "status": random.choice(cart_statuses), 
                    "total_amount": 0.0
                } 
                for _ in range(100000)
            ]
            db.execute(insert(Cart), cart_data)
            db.commit()
            print(f"  -> Inserted { (chunk + 1) * 100000 } Carts")

        # 4. Seed 3,900,000 Cart Items (Chunked to save RAM)
        print("Seeding 3,900,000 Cart Items (in chunks of 100,000)...")
        for chunk in range(39): 
            item_data = [
                {
                    "cart_id": random.randint(1, 1000000), 
                    "product_id": random.randint(1, 10000), 
                    "quantity": random.randint(1, 5), 
                    "price_at_addition": round(random.uniform(10.0, 500.0), 2)
                } 
                for _ in range(100000)
            ]
            db.execute(insert(CartItem), item_data)
            db.commit()
            print(f"  -> Inserted { (chunk + 1) * 100000 } Cart Items")

        end_time = time.time()
        print(f"BOOM! ~5 Million Rows seeded successfully in {round(end_time - start_time, 2)} seconds.")

    except Exception as e:
        print(f" Error during mass seeding: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_massive_data()