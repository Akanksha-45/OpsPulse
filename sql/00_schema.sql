-- OpsPulse - Warehouse schema (PostgreSQL)
-- Layered design:
--   staging_*  : raw ingestion, NO constraints (mirrors source extracts, includes defects)
--   public.*   : clean mart, enforced keys/constraints (governed by data-quality rules)
--   data_quality_audit : a log of every rejected / flagged raw row and why

-- ============================= STAGING (raw) =============================

DROP TABLE IF EXISTS staging_sla_rules CASCADE;
DROP TABLE IF EXISTS staging_escalations CASCADE;
DROP TABLE IF EXISTS staging_ticket_status_history CASCADE;
DROP TABLE IF EXISTS staging_tickets CASCADE;
DROP TABLE IF EXISTS staging_agents CASCADE;
DROP TABLE IF EXISTS staging_customers CASCADE;
DROP TABLE IF EXISTS data_quality_audit CASCADE;

CREATE TABLE staging_customers (
    customer_id         TEXT, customer_segment TEXT, region TEXT, customer_value_kusd TEXT
);
CREATE TABLE staging_agents (
    agent_id TEXT, department TEXT, team TEXT, experience_level TEXT,
    shift TEXT, location TEXT, capacity_per_day TEXT
);
CREATE TABLE staging_tickets (
    ticket_id TEXT, customer_id TEXT, created_at TEXT, priority TEXT, category TEXT,
    channel TEXT, department TEXT, assigned_agent TEXT, sla_hours TEXT,
    response_sla_hours TEXT, status TEXT, resolved_at TEXT, first_response_at TEXT,
    escalation_required TEXT, reopened TEXT, resolution_time_hours TEXT, sla_breach TEXT
);
CREATE TABLE staging_ticket_status_history (
    ticket_id TEXT, status TEXT, start_time TEXT, end_time TEXT, duration_hours TEXT
);
CREATE TABLE staging_escalations (
    escalation_id TEXT, ticket_id TEXT, escalation_type TEXT, escalated_at TEXT, reason TEXT
);
CREATE TABLE staging_sla_rules (
    priority TEXT, customer_segment TEXT, sla_hours TEXT, response_hours TEXT
);

CREATE TABLE data_quality_audit (
    audit_id        SERIAL PRIMARY KEY,
    source_table    TEXT NOT NULL,
    row_key         TEXT,
    issue           TEXT NOT NULL,
    detail          TEXT,
    logged_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================= CLEAN MART =============================

DROP TABLE IF EXISTS sla_rules CASCADE;
DROP TABLE IF EXISTS escalations CASCADE;
DROP TABLE IF EXISTS ticket_status_history CASCADE;
DROP TABLE IF EXISTS tickets CASCADE;
DROP TABLE IF EXISTS agents CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

CREATE TABLE customers (
    customer_id         TEXT PRIMARY KEY,
    customer_segment    TEXT NOT NULL,
    region              TEXT NOT NULL,
    customer_value_kusd NUMERIC(10,2) NOT NULL
);

CREATE TABLE agents (
    agent_id         TEXT PRIMARY KEY,
    department       TEXT NOT NULL,
    team             TEXT NOT NULL,
    experience_level TEXT NOT NULL,
    shift            TEXT NOT NULL,
    location         TEXT NOT NULL,
    capacity_per_day INTEGER NOT NULL
);

CREATE TABLE tickets (
    ticket_id            TEXT PRIMARY KEY,
    customer_id          TEXT NOT NULL REFERENCES customers(customer_id),
    created_at           TIMESTAMP NOT NULL,
    priority             TEXT NOT NULL,
    category             TEXT NOT NULL,
    channel              TEXT,
    department           TEXT NOT NULL,
    assigned_agent       TEXT REFERENCES agents(agent_id),
    sla_hours            NUMERIC(8,2) NOT NULL,
    response_sla_hours   NUMERIC(8,2) NOT NULL,
    status               TEXT NOT NULL,
    resolved_at          TIMESTAMP,
    first_response_at    TIMESTAMP,
    escalation_required  BOOLEAN NOT NULL DEFAULT FALSE,
    reopened             BOOLEAN NOT NULL DEFAULT FALSE,
    resolution_time_hours NUMERIC(10,3),
    sla_breach           BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_tickets_created ON tickets (created_at);
CREATE INDEX idx_tickets_dept    ON tickets (department);
CREATE INDEX idx_tickets_priority ON tickets (priority);

CREATE TABLE ticket_status_history (
    ticket_id      TEXT NOT NULL REFERENCES tickets(ticket_id),
    status         TEXT NOT NULL,
    start_time     TIMESTAMP NOT NULL,
    end_time       TIMESTAMP NOT NULL,
    duration_hours NUMERIC(10,3),
    PRIMARY KEY (ticket_id, status, start_time)
);

CREATE INDEX idx_history_ticket ON ticket_status_history (ticket_id);
CREATE INDEX idx_history_status ON ticket_status_history (status);

CREATE TABLE escalations (
    escalation_id    TEXT PRIMARY KEY,
    ticket_id        TEXT NOT NULL REFERENCES tickets(ticket_id),
    escalation_type  TEXT NOT NULL,
    escalated_at     TIMESTAMP NOT NULL,
    reason           TEXT NOT NULL
);

CREATE TABLE sla_rules (
    priority         TEXT NOT NULL,
    customer_segment TEXT NOT NULL,
    sla_hours        NUMERIC(8,2) NOT NULL,
    response_hours   NUMERIC(8,2) NOT NULL,
    PRIMARY KEY (priority, customer_segment)
);