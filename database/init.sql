-- ====================================================
-- CLEAR STALE STRUCTURES COMPLETELY
-- ====================================================
DROP TABLE IF EXISTS subscription_schedule CASCADE;
DROP TABLE IF EXISTS subscriptions CASCADE;
DROP TABLE IF EXISTS daily_logs CASCADE;
DROP TABLE IF EXISTS order_item_ingredients CASCADE;
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS meal_ingredients CASCADE;
DROP TABLE IF EXISTS ingredients CASCADE;
DROP TABLE IF EXISTS meals CASCADE;
DROP TABLE IF EXISTS vendors CASCADE;
DROP TABLE IF EXISTS macro_profiles CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- ====================================================
-- FOOD GORILLA - CORE SCHEMA
-- ====================================================

CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Feature 1: User Macro Calculator & Profile
CREATE TABLE macro_profiles (
    profile_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id) ON DELETE CASCADE,
    daily_calorie_target INT NOT NULL,
    target_protein_g INT NOT NULL,
    target_carbs_g INT NOT NULL,
    target_fats_g INT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Feature 5: Vendor Nutritional Portal
CREATE TABLE vendors (
    vendor_id SERIAL PRIMARY KEY,
    restaurant_name VARCHAR(100) NOT NULL,
    cuisine_type VARCHAR(50),
    is_verified BOOLEAN DEFAULT FALSE
);

-- Feature 2: Smart Nutritional Search & Filter (base macro columns live here)
CREATE TABLE meals (
    meal_id SERIAL PRIMARY KEY,
    vendor_id INT REFERENCES vendors(vendor_id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    base_price DECIMAL(10, 2) NOT NULL,
    base_calories INT NOT NULL,
    base_protein INT NOT NULL,
    base_carbs INT NOT NULL,
    base_fats INT NOT NULL
);

-- Feature 3: Custom Meal-Builder CRUD
CREATE TABLE ingredients (
    ingredient_id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    unit VARCHAR(20) DEFAULT 'grams',
    calories_per_unit INT NOT NULL,
    protein_per_unit INT NOT NULL,
    carbs_per_unit INT NOT NULL,
    fats_per_unit INT NOT NULL,
    price_per_unit DECIMAL(10, 2) NOT NULL
);

-- Default recipe for a meal (what it ships with before any swaps)
CREATE TABLE meal_ingredients (
    meal_id INT REFERENCES meals(meal_id) ON DELETE CASCADE,
    ingredient_id INT REFERENCES ingredients(ingredient_id) ON DELETE CASCADE,
    default_quantity INT NOT NULL,
    PRIMARY KEY (meal_id, ingredient_id)
);

-- ====================================================
-- ORDERS (connects meal-builder output to the dashboard + subscriptions)
-- ====================================================

CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id) ON DELETE CASCADE,
    vendor_id INT REFERENCES vendors(vendor_id),
    order_status VARCHAR(20) DEFAULT 'pending', -- pending / confirmed / out_for_delivery / delivered
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_price DECIMAL(10, 2) NOT NULL,
    total_calories INT NOT NULL,
    total_protein INT NOT NULL,
    total_carbs INT NOT NULL,
    total_fats INT NOT NULL
);

-- One row per meal within an order. Price/macros are snapshotted here
-- (copied in at order time) so a later edit to a meal's base recipe
-- never changes the numbers on a past order.
CREATE TABLE order_items (
    order_item_id SERIAL PRIMARY KEY,
    order_id INT REFERENCES orders(order_id) ON DELETE CASCADE,
    meal_id INT REFERENCES meals(meal_id),
    quantity INT NOT NULL DEFAULT 1,
    item_price DECIMAL(10, 2) NOT NULL,
    item_calories INT NOT NULL,
    item_protein INT NOT NULL,
    item_carbs INT NOT NULL,
    item_fats INT NOT NULL
);

-- Snapshot of the ACTUAL ingredient customization used for this order item
-- (e.g. "swapped white rice for broccoli") — independent of meal_ingredients,
-- so past orders stay accurate even if the meal's default recipe changes later.
CREATE TABLE order_item_ingredients (
    order_item_id INT REFERENCES order_items(order_item_id) ON DELETE CASCADE,
    ingredient_id INT REFERENCES ingredients(ingredient_id),
    quantity INT NOT NULL,
    PRIMARY KEY (order_item_id, ingredient_id)
);

-- Feature 4: Daily Target Tracker (Dashboard)
-- Aggregate rollup per user per day; app logic populates this from orders.
CREATE TABLE daily_logs (
    log_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id) ON DELETE CASCADE,
    log_date DATE DEFAULT CURRENT_DATE,
    total_calories_consumed INT DEFAULT 0,
    total_protein_consumed INT DEFAULT 0,
    total_carbs_consumed INT DEFAULT 0,
    total_fats_consumed INT DEFAULT 0
);

-- Feature 6: Automated Subscriptions/Scheduled Orders
CREATE TABLE subscriptions (
    subscription_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id) ON DELETE CASCADE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'active'
);

CREATE TABLE subscription_schedule (
    schedule_id SERIAL PRIMARY KEY,
    subscription_id INT REFERENCES subscriptions(subscription_id) ON DELETE CASCADE,
    delivery_day_of_week INT NOT NULL,
    meal_id INT REFERENCES meals(meal_id),
    delivery_time_slot VARCHAR(20) NOT NULL
);

-- ====================================================
-- SEED DATA
-- (No hardcoded IDs / setval() calls — inserts look up IDs by name via
-- subqueries, so the seed data survives fine no matter what order Postgres
-- assigns SERIAL values in.)
-- ====================================================

INSERT INTO vendors (restaurant_name, cuisine_type, is_verified)
VALUES ('Lean & Mean Kitchen', 'Healthy Western', true);

INSERT INTO meals (vendor_id, name, description, base_price, base_calories, base_protein, base_carbs, base_fats)
VALUES (
    (SELECT vendor_id FROM vendors WHERE restaurant_name = 'Lean & Mean Kitchen'),
    'Sous-Vide Chicken Breast Bowl',
    'Fluffy brown rice paired with clean chicken breast and broccoli.',
    12.50, 520, 45, 50, 10
);

INSERT INTO ingredients (name, unit, calories_per_unit, protein_per_unit, carbs_per_unit, fats_per_unit, price_per_unit)
VALUES
    ('Extra Chicken Breast', '50g', 82, 15, 0, 1, 2.50),
    ('Avocado Scoop', '30g', 48, 1, 3, 4, 1.80);

INSERT INTO meal_ingredients (meal_id, ingredient_id, default_quantity)
SELECT m.meal_id, i.ingredient_id, 1
FROM meals m, ingredients i
WHERE m.name = 'Sous-Vide Chicken Breast Bowl'
  AND i.name IN ('Extra Chicken Breast', 'Avocado Scoop');