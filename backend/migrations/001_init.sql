-- ============================================
-- Database schema for marketplace
-- Lab 01 base + Lab 02 requirements
-- ============================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Status lookup table
CREATE TABLE IF NOT EXISTS order_statuses (
    status VARCHAR(20) PRIMARY KEY,
    description TEXT
);

-- Insert status values
INSERT INTO order_statuses (status, description) VALUES
    ('created', 'Order created'),
    ('paid', 'Order paid'),
    ('cancelled', 'Order cancelled'),
    ('shipped', 'Order shipped'),
    ('completed', 'Order completed')
ON CONFLICT (status) DO NOTHING;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT email_format_check CHECK (
        email ~ '^[a-zA-Z0-9][a-zA-Z0-9._%-]*@[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,}$'
    )
);

-- Orders table
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL REFERENCES order_statuses(status),
    total_amount NUMERIC(15, 2) NOT NULL DEFAULT 0.00 CHECK (total_amount >= 0),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Order items table
CREATE TABLE IF NOT EXISTS order_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_name VARCHAR(255) NOT NULL CHECK (LENGTH(TRIM(product_name)) > 0),
    price NUMERIC(15, 2) NOT NULL CHECK (price >= 0),
    quantity INTEGER NOT NULL CHECK (quantity > 0)
);

-- Order status history table
CREATE TABLE IF NOT EXISTS order_status_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL REFERENCES order_statuses(status),
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- CRITICAL INVARIANT: Cannot pay order twice
-- ============================================
-- Trigger function to check double payment
CREATE OR REPLACE FUNCTION check_order_not_already_paid() 
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'paid' THEN
        IF EXISTS (
            SELECT 1 FROM order_status_history
            WHERE order_id = NEW.id AND status = 'paid'
        ) THEN
            RAISE EXCEPTION 'Order % is already paid', NEW.id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger on order update
CREATE TRIGGER trigger_check_order_not_already_paid
    BEFORE UPDATE ON orders
    FOR EACH ROW
    WHEN (NEW.status <> OLD.status)
    EXECUTE FUNCTION check_order_not_already_paid();

-- ============================================
-- Bonus triggers (optional)
-- ============================================

-- Auto-update total_amount when items change
CREATE OR REPLACE FUNCTION update_order_total_amount() 
RETURNS TRIGGER AS $$
BEGIN
    UPDATE orders
    SET total_amount = (
        SELECT COALESCE(SUM(price * quantity), 0)
        FROM order_items
        WHERE order_id = COALESCE(NEW.order_id, OLD.order_id)
    )
    WHERE id = COALESCE(NEW.order_id, OLD.order_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_order_total_after_item_change
    AFTER INSERT OR UPDATE OR DELETE ON order_items
    FOR EACH ROW
    EXECUTE FUNCTION update_order_total_amount();

-- Auto-log status changes
CREATE OR REPLACE FUNCTION log_order_status_change() 
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status <> OLD.status THEN
        INSERT INTO order_status_history (order_id, status, changed_at)
        VALUES (NEW.id, NEW.status, CURRENT_TIMESTAMP);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_log_order_status_change
    AFTER UPDATE ON orders
    FOR EACH ROW
    EXECUTE FUNCTION log_order_status_change();

-- Auto-log initial status on order creation
CREATE OR REPLACE FUNCTION insert_initial_order_status() 
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO order_status_history (order_id, status, changed_at)
    VALUES (NEW.id, NEW.status, NEW.created_at);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_insert_initial_order_status
    AFTER INSERT ON orders
    FOR EACH ROW
    EXECUTE FUNCTION insert_initial_order_status();
