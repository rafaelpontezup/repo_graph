-- Common queries for the CRUD application

-- User queries
-- name: find_user_by_id
SELECT id, name, email, password_hash, status, created_at, updated_at
FROM users
WHERE id = :user_id;

-- name: find_user_by_email
SELECT id, name, email, password_hash, status, created_at, updated_at
FROM users
WHERE email = :email;

-- name: find_all_users
SELECT id, name, email, password_hash, status, created_at, updated_at
FROM users
ORDER BY created_at DESC
LIMIT :limit OFFSET :offset;

-- name: insert_user
INSERT INTO users (name, email, password_hash, status, created_at)
VALUES (:name, :email, :password_hash, :status, :created_at);

-- name: update_user
UPDATE users
SET name = :name, email = :email, password_hash = :password_hash, 
    status = :status, updated_at = :updated_at
WHERE id = :user_id;

-- name: delete_user
DELETE FROM users WHERE id = :user_id;


-- Product queries
-- name: find_product_by_id
SELECT id, name, description, price, stock_quantity, is_available, created_at, updated_at
FROM products
WHERE id = :product_id;

-- name: find_available_products
SELECT id, name, description, price, stock_quantity, is_available, created_at, updated_at
FROM products
WHERE is_available = 1 AND stock_quantity > 0
ORDER BY name ASC;

-- name: search_products_by_name
SELECT id, name, description, price, stock_quantity, is_available, created_at, updated_at
FROM products
WHERE name LIKE '%' || :search_term || '%'
ORDER BY name ASC;

-- name: update_product_stock
UPDATE products
SET stock_quantity = stock_quantity + :quantity_delta, updated_at = :updated_at
WHERE id = :product_id;


-- Order queries
-- name: find_order_with_items
SELECT 
    o.id AS order_id,
    o.user_id,
    o.status,
    o.created_at AS order_created_at,
    o.updated_at AS order_updated_at,
    oi.id AS item_id,
    oi.product_id,
    oi.product_name,
    oi.quantity,
    oi.unit_price
FROM orders o
LEFT JOIN order_items oi ON o.id = oi.order_id
WHERE o.id = :order_id;

-- name: find_orders_by_user
SELECT id, user_id, status, created_at, updated_at
FROM orders
WHERE user_id = :user_id
ORDER BY created_at DESC;

-- name: count_orders_by_status
SELECT status, COUNT(*) AS total
FROM orders
GROUP BY status;

-- name: calculate_order_total
SELECT SUM(quantity * unit_price) AS total_amount
FROM order_items
WHERE order_id = :order_id;

-- name: get_sales_report
SELECT 
    DATE(o.created_at) AS sale_date,
    COUNT(DISTINCT o.id) AS total_orders,
    SUM(oi.quantity) AS total_items,
    SUM(oi.quantity * oi.unit_price) AS total_revenue
FROM orders o
JOIN order_items oi ON o.id = oi.order_id
WHERE o.status IN ('confirmed', 'shipped', 'delivered')
  AND o.created_at BETWEEN :start_date AND :end_date
GROUP BY DATE(o.created_at)
ORDER BY sale_date DESC;
