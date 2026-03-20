-- ============================================
-- SQL Migrator Dry-run 테스트용 스키마 & 샘플 데이터
-- DB: sql_migrator_target (PostgreSQL 15)
-- ============================================

-- ────────────────────────────────────────────
-- 1. TB_USER (level1, level3에서 참조)
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tb_user (
    user_id     SERIAL PRIMARY KEY,
    user_name   VARCHAR(100) NOT NULL,
    email       VARCHAR(200),
    phone       VARCHAR(50),
    use_yn      CHAR(1) DEFAULT 'Y',
    reg_date    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mod_date    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO tb_user (user_name, email, phone, use_yn) VALUES
('홍길동', 'hong@example.com', '010-1234-5678', 'Y'),
('김철수', 'kim@example.com', '010-2345-6789', 'Y'),
('이영희', NULL, '010-3456-7890', 'Y'),
('박민수', 'park@example.com', NULL, 'Y'),
('최지현', 'choi@example.com', '010-5678-9012', 'N');

-- ────────────────────────────────────────────
-- 2. TB_CUSTOMER (level2, level3에서 참조)
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tb_customer (
    cust_id     SERIAL PRIMARY KEY,
    cust_name   VARCHAR(100) NOT NULL,
    phone       VARCHAR(50),
    dept_id     VARCHAR(20),
    reg_date    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO tb_customer (cust_name, phone, dept_id) VALUES
('SK브로드밴드', '02-1234-5678', 'DEPT01'),
('KT', '02-2345-6789', 'DEPT02'),
('LG유플러스', '02-3456-7890', 'DEPT01'),
('Samsung SDS', '02-4567-8901', 'DEPT03'),
('네이버', '031-123-4567', 'DEPT02');

-- ────────────────────────────────────────────
-- 3. TB_ORDER (level2, level3에서 참조)
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tb_order (
    order_id    SERIAL PRIMARY KEY,
    cust_id     INTEGER REFERENCES tb_customer(cust_id),
    order_date  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    total_amt   NUMERIC(15,2) DEFAULT 0,
    status      VARCHAR(10) DEFAULT '01',
    memo        TEXT,
    reg_date    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO tb_order (cust_id, order_date, total_amt, status, memo) VALUES
(1, '2026-01-15 10:00:00', 500000, '01', '첫 주문'),
(1, '2026-02-20 14:30:00', 1500000, '03', 'VIP 주문'),
(2, '2026-01-10 09:00:00', 300000, '02', NULL),
(3, '2026-03-01 11:00:00', 2000000, '03', '대량 주문 건'),
(4, '2026-02-15 16:00:00', 750000, '01', NULL),
(5, '2026-03-10 13:00:00', 100000, '99', '취소된 주문'),
(1, '2026-03-05 10:00:00', 800000, '02', NULL),
(2, '2026-03-08 15:00:00', 450000, '03', '배송 완료');

-- ────────────────────────────────────────────
-- 4. TB_PRODUCT (level3에서 참조)
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tb_product (
    prod_id     SERIAL PRIMARY KEY,
    prod_code   VARCHAR(50) NOT NULL,
    prod_name   VARCHAR(200) NOT NULL,
    price       NUMERIC(15,2) DEFAULT 0,
    use_yn      CHAR(1) DEFAULT 'Y'
);

INSERT INTO tb_product (prod_code, prod_name, price) VALUES
('PRD001', '인터넷 100M', 30000),
('PRD002', '인터넷 500M', 40000),
('PRD003', '인터넷 1G', 50000),
('PRD004', 'IPTV 기본', 15000),
('PRD005', 'IPTV 프리미엄', 25000);

-- ────────────────────────────────────────────
-- 5. TB_ORDER_PROD (level3에서 참조)
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tb_order_prod (
    order_id    INTEGER REFERENCES tb_order(order_id),
    prod_id     INTEGER REFERENCES tb_product(prod_id),
    qty         INTEGER DEFAULT 1,
    PRIMARY KEY (order_id, prod_id)
);

INSERT INTO tb_order_prod (order_id, prod_id, qty) VALUES
(1, 1, 1), (1, 4, 1),
(2, 3, 1), (2, 5, 1),
(3, 2, 1),
(4, 3, 2), (4, 4, 1), (4, 5, 1),
(5, 1, 1),
(6, 1, 1),
(7, 2, 1), (7, 4, 1),
(8, 3, 1);

-- ────────────────────────────────────────────
-- 6. TB_ORG (level3 계층 쿼리에서 참조)
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tb_org (
    org_id          VARCHAR(20) PRIMARY KEY,
    org_name        VARCHAR(100) NOT NULL,
    parent_org_id   VARCHAR(20),
    sort_order      INTEGER DEFAULT 0
);

INSERT INTO tb_org (org_id, org_name, parent_org_id, sort_order) VALUES
('ORG001', '본사', NULL, 1),
('ORG002', '개발본부', 'ORG001', 1),
('ORG003', '영업본부', 'ORG001', 2),
('ORG004', '백엔드팀', 'ORG002', 1),
('ORG005', '프론트엔드팀', 'ORG002', 2),
('ORG006', '국내영업팀', 'ORG003', 1),
('ORG007', '해외영업팀', 'ORG003', 2);

-- ────────────────────────────────────────────
-- 7. TB_USER_STATS (level3 MERGE 쿼리에서 참조)
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tb_user_stats (
    user_id     INTEGER NOT NULL,
    stat_date   DATE NOT NULL,
    login_cnt   INTEGER DEFAULT 0,
    page_view   INTEGER DEFAULT 0,
    reg_date    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mod_date    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, stat_date)
);

INSERT INTO tb_user_stats (user_id, stat_date, login_cnt, page_view) VALUES
(1, '2026-03-01', 5, 120),
(1, '2026-03-02', 3, 80),
(2, '2026-03-01', 2, 45),
(3, '2026-03-01', 8, 200);

-- ────────────────────────────────────────────
-- 8. TB_PLAN (mixed_all_levels에서 참조)
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tb_plan (
    plan_id         VARCHAR(20) PRIMARY KEY,
    plan_name       VARCHAR(200) NOT NULL,
    plan_type       CHAR(1) DEFAULT 'A',
    description     TEXT,
    parent_plan_id  VARCHAR(20),
    start_date      TIMESTAMP,
    use_yn          CHAR(1) DEFAULT 'Y',
    reg_date        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO tb_plan (plan_id, plan_name, plan_type, description, parent_plan_id, start_date, use_yn) VALUES
('PLN001', '기본 요금제', 'A', '월 30,000원 기본형', NULL, '2026-01-01', 'Y'),
('PLN002', '프리미엄 요금제', 'B', '월 50,000원 프리미엄', NULL, '2026-01-01', 'Y'),
('PLN003', '기본 인터넷', 'A', '100Mbps 인터넷', 'PLN001', '2026-01-01', 'Y'),
('PLN004', '기본 IPTV', 'A', 'IPTV 기본 채널', 'PLN001', '2026-02-01', 'Y'),
('PLN005', '프리미엄 인터넷', 'B', '1Gbps 인터넷', 'PLN002', '2026-01-01', 'Y'),
('PLN006', '프리미엄 IPTV', 'B', 'IPTV 전체 채널', 'PLN002', '2026-02-01', 'Y'),
('PLN007', '엔터프라이즈', 'C', '기업용 통합 패키지', NULL, '2026-03-01', 'Y'),
('PLN_OLD', '구형 요금제', 'A', '단종 요금제', NULL, '2025-01-01', 'N');

-- ────────────────────────────────────────────
-- 9. TB_PLAN_DETAIL (mixed_all_levels에서 참조)
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tb_plan_detail (
    plan_id     VARCHAR(20) REFERENCES tb_plan(plan_id),
    detail_seq  INTEGER DEFAULT 1,
    detail_desc TEXT,
    PRIMARY KEY (plan_id, detail_seq)
);

INSERT INTO tb_plan_detail (plan_id, detail_seq, detail_desc) VALUES
('PLN001', 1, '기본 데이터 제공'),
('PLN002', 1, '무제한 데이터 + 부가서비스'),
('PLN003', 1, '100Mbps 대역폭 보장'),
('PLN005', 1, '1Gbps 대역폭 + 고정 IP'),
('PLN007', 1, '전용선급 서비스');

-- ────────────────────────────────────────────
-- 10. TB_PLAN_STATS (mixed_all_levels MERGE에서 참조)
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tb_plan_stats (
    plan_id     VARCHAR(20) PRIMARY KEY REFERENCES tb_plan(plan_id),
    view_cnt    INTEGER DEFAULT 0,
    reg_date    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mod_date    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO tb_plan_stats (plan_id, view_cnt) VALUES
('PLN001', 150),
('PLN002', 230),
('PLN003', 80);

-- ────────────────────────────────────────────
-- 시퀀스 (level1 .NEXTVAL 변환 테스트용)
-- ────────────────────────────────────────────
CREATE SEQUENCE IF NOT EXISTS user_seq START WITH 100 INCREMENT BY 1;
