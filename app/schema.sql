CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    display_name TEXT NOT NULL CHECK (length(display_name) BETWEEN 2 AND 40),
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'moderator', 'admin')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE
);

INSERT OR IGNORE INTO categories (name, slug) VALUES
    ('Züge', 'zuege'), ('Häuser', 'haeuser'), ('Dekoobjekte', 'deko'),
    ('Maschinen & Fabriken', 'maschinen'), ('Farmen', 'farmen'),
    ('Brücken & Infrastruktur', 'infrastruktur'), ('Fahrzeuge', 'fahrzeuge'),
    ('Sonstiges', 'sonstiges');

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY,
    owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    title TEXT NOT NULL CHECK (length(title) BETWEEN 3 AND 100),
    description TEXT NOT NULL CHECK (length(description) BETWEEN 10 AND 10000),
    image_filename TEXT NOT NULL,
    schematic_filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    approved_at TEXT,
    approved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS likes (
    post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (post_id, user_id)
);

CREATE TABLE IF NOT EXISTS login_attempts (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL,
    address TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_posts_owner ON posts(owner_id);
CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category_id);
CREATE INDEX IF NOT EXISTS idx_likes_user ON likes(user_id);
CREATE INDEX IF NOT EXISTS idx_login_attempts_time ON login_attempts(created_at);
