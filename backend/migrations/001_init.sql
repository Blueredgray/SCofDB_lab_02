-- Миграция: начальная схема БД маркетплейса
-- Создаёт таблицы users, orders, order_items, order_statuses, order_status_history

-- Справочник статусов заказов
CREATE TABLE IF NOT EXISTS order_statuses (
    status VARCHAR(20) PRIMARY KEY,
    description TEXT
);

INSERT INTO order_statuses (status, description) VALUES
    ('created', 'Заказ создан'),
    ('paid', 'Заказ оплачен'),
    ('cancelled', 'Заказ отменен'),
    ('shipped', 'Заказ отправлен'),
    ('completed', 'Заказ завершен')
ON CONFLICT (status) DO NOTHING;

-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_email CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

-- Таблица заказов
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'created' REFERENCES order_statuses(status),
    total_amount DECIMAL(10, 2) NOT NULL DEFAULT 0.0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT positive_total CHECK (total_amount >= 0)
);

-- Таблица позиций заказа
CREATE TABLE IF NOT EXISTS order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_name VARCHAR(255) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    quantity INTEGER NOT NULL,
    CONSTRAINT positive_price CHECK (price >= 0),
    CONSTRAINT positive_quantity CHECK (quantity > 0)
);

-- Таблица истории изменения статусов
CREATE TABLE IF NOT EXISTS order_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL REFERENCES order_statuses(status),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для производительности
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_status_history_order_id ON order_status_history(order_id);