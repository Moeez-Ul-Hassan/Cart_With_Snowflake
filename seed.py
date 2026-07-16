import random
import time
from sqlalchemy import insert
from app.database.session import SessionLocal
from app.models.domain import User, Product, Cart, CartItem

def seed_massive_data():
    db = SessionLocal()
    BATCH_SIZE = 1000
    try:
        print("🚀 Starting Enterprise Data Generation (1 Million Rows / 1k Batches)...")
        start_time = time.time()

        # 1. Seed 10,000 Users (10 batches of 1,000)
        print("Seeding 10,000 Users...")
        for chunk in range(10):
            start_id = (chunk * BATCH_SIZE) + 1
            end_id = start_id + BATCH_SIZE
            user_data = [{"email": f"user{i}@nomixtrade.com", "name": f"User {i}"} for i in range(start_id, end_id)]
            db.execute(insert(User), user_data)
            db.commit()
            print(f"  -> Inserted { (chunk + 1) * BATCH_SIZE } Users")

        # 2. Seed 1,000 Products (1 batch of 1,000)
        print("Seeding 1,000 Products...")
        product_data = [
            {
                "name": f"Enterprise Product {i}", 
                "price": round(random.uniform(10.0, 5000.0), 2), 
                "stock": random.randint(10, 1000), 
                "reserved_stock": 0
            } 
            for i in range(1, 1001)
        ]
        db.execute(insert(Product), product_data)
        db.commit()
        print("Inserted 1000 Products")

        # 3. Seed 200,000 Carts (200 batches of 1,000)
        print("Seeding 200,000 Carts...")
        cart_statuses = ["active", "checked_out", "abandoned"]
        for chunk in range(200): 
            cart_data = [
                {
                    "user_id": random.randint(1, 10000), 
                    "status": random.choice(cart_statuses), 
                    "total_amount": 0.0
                } 
                for _ in range(BATCH_SIZE)
            ]
            db.execute(insert(Cart), cart_data)
            db.commit()
            if (chunk + 1) % 50 == 0: # Print every 50k to keep terminal clean
                print(f"  -> Inserted { (chunk + 1) * BATCH_SIZE } Carts")

        # 4. Seed 800,000 Cart Items (800 batches of 1,000)
        print("Seeding 800,000 Cart Items...")
        for chunk in range(800): 
            item_data = [
                {
                    "cart_id": random.randint(1, 200000), 
                    "product_id": random.randint(1, 1000), 
                    "quantity": random.randint(1, 5), 
                    "price_at_addition": round(random.uniform(10.0, 500.0), 2)
                } 
                for _ in range(BATCH_SIZE)
            ]
            db.execute(insert(CartItem), item_data)
            db.commit()
            if (chunk + 1) % 100 == 0: # Print every 100k
                print(f"  -> Inserted { (chunk + 1) * BATCH_SIZE } Cart Items")

        end_time = time.time()
        print(f"✅ BOOM! ~1 Million Rows seeded successfully in {round(end_time - start_time, 2)} seconds.")

    except Exception as e:
        print(f"❌ Error during mass seeding: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_massive_data()