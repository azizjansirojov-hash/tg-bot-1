-- Manual retention for admin_audit_log (example: 90 days).
-- Run via psql / your host's scheduled job — not automated by the bot process.
DELETE FROM admin_audit_log
WHERE timestamp < NOW() - INTERVAL '90 days';
