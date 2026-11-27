-- Lược đồ khởi đầu của API (D1). Thời gian: ms epoch UTC, trừ `rate.window_start` (giây epoch).
-- Mỗi migration sau là một file mới `000N_<tên>.sql` — KHÔNG sửa file đã chạy trên prod.

-- Bộ đếm giới hạn tần suất, cửa sổ cố định (src/rate.ts).
CREATE TABLE rate (
  key TEXT PRIMARY KEY,
  window_start INTEGER NOT NULL,
  count INTEGER NOT NULL
);

-- Phản hồi từ app (POST /api/v1/feedback). KHÔNG có IP hay định danh nào ngoài những gì người dùng tự gõ.
CREATE TABLE feedback (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  message TEXT NOT NULL,
  email TEXT NOT NULL DEFAULT '',
  diagnostics TEXT NOT NULL DEFAULT '',
  app_version TEXT NOT NULL,
  client_time INTEGER NOT NULL,
  created_at INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  note TEXT NOT NULL DEFAULT '',
  updated_at INTEGER NOT NULL
);
CREATE INDEX feedback_status_created ON feedback(status, created_at);

-- Web analytics không cookie: GỘP theo ngày, mọi chiều là tập hữu hạn — không IP, user-agent hay URL đầy đủ.
-- '-' = chiều không áp dụng cho sự kiện đó.
CREATE TABLE web_events (
  day     TEXT NOT NULL,     -- 'YYYYMMDD' (UTC)
  page    TEXT NOT NULL,
  event   TEXT NOT NULL,
  detail  TEXT NOT NULL,
  source  TEXT NOT NULL,
  country TEXT NOT NULL,     -- ISO-3166 alpha-2, 'XX' khi không rõ
  device  TEXT NOT NULL,     -- ios | android | desktop
  n       INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (day, page, event, detail, source, country, device)
);

-- Tên miền gửi khách tới (chỉ hostname, hoặc 'utm:<giá trị>').
CREATE TABLE web_referrers (
  day    TEXT NOT NULL,
  domain TEXT NOT NULL,
  n      INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (day, domain)
);

-- App Store Server Notifications V2 — CHỈ GHI sự kiện gói. Không lưu JWS thô, không appAccountToken.
CREATE TABLE appstore_notifications (
  notification_uuid TEXT PRIMARY KEY,
  notification_type TEXT NOT NULL,
  subtype TEXT,
  environment TEXT NOT NULL,
  signed_date INTEGER NOT NULL,
  received_at INTEGER NOT NULL,
  original_tx_id TEXT,
  transaction_id TEXT,
  product_id TEXT,
  purchase_date INTEGER,
  expires_date INTEGER,
  revocation_date INTEGER,
  revocation_reason INTEGER,
  offer_type INTEGER,
  price INTEGER,
  currency TEXT,
  storefront TEXT,
  auto_renew_status INTEGER,
  auto_renew_product_id TEXT,
  expiration_intent INTEGER,
  grace_period_expires_date INTEGER
);
CREATE INDEX appstore_notifications_tx ON appstore_notifications(original_tx_id, signed_date);
CREATE INDEX appstore_notifications_received ON appstore_notifications(received_at);
