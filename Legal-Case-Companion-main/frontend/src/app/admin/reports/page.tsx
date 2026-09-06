"use client";

import React from "react";
import { Card, Badge, Table, Button } from "@/components/ui";

export default function AdminReportsPage() {
  return (
    <div style={{ maxWidth: "1280px", margin: "0 auto", padding: "24px 20px" }}>
      <div style={{ marginBottom: "24px" }}>
        <h1
          style={{
            fontSize: "var(--font-size-2xl, 24px)",
            fontWeight: 700,
            color: "var(--text-primary, #f8fafc)",
            fontFamily: "var(--font-display, sans-serif)",
            margin: "0 0 6px 0",
          }}
        >
          Practice Analytics & Matter Reports
        </h1>
        <p style={{ fontSize: "var(--font-size-sm, 14px)", color: "var(--text-secondary, #94a3b8)", margin: 0 }}>
          High-level operational metrics on case progression, court listing turnaround times, and statutory compliance.
        </p>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
          gap: "16px",
          marginBottom: "28px",
        }}
      >
        <Card variant="elevated" padding="md">
          <div style={{ fontSize: "12px", color: "var(--text-muted, #64748b)", textTransform: "uppercase", fontWeight: 600 }}>
            Total Active Matters
          </div>
          <div style={{ fontSize: "32px", fontWeight: 700, marginTop: "4px" }}>
            24
          </div>
          <div style={{ fontSize: "12px", color: "var(--success, #10B981)", marginTop: "4px" }}>
            Across 4 Judicial Forums
          </div>
        </Card>

        <Card variant="elevated" padding="md">
          <div style={{ fontSize: "12px", color: "var(--text-muted, #64748b)", textTransform: "uppercase", fontWeight: 600 }}>
            Hearings This Month
          </div>
          <div style={{ fontSize: "32px", fontWeight: 700, marginTop: "4px" }}>
            18
          </div>
          <div style={{ fontSize: "12px", color: "var(--info, #06B6D4)", marginTop: "4px" }}>
            100% Cause List Synchronized
          </div>
        </Card>

        <Card variant="elevated" padding="md">
          <div style={{ fontSize: "12px", color: "var(--text-muted, #64748b)", textTransform: "uppercase", fontWeight: 600 }}>
            Statutory Limitations Monitored
          </div>
          <div style={{ fontSize: "32px", fontWeight: 700, marginTop: "4px" }}>
            6
          </div>
          <div style={{ fontSize: "12px", color: "var(--warning, #F59E0B)", marginTop: "4px" }}>
            0 Overdue / Breached
          </div>
        </Card>
      </div>

      <Card variant="default" padding="lg">
        <Card.Header
          title="Forum Disposal Performance"
          subtitle="Matters tracked across Delhi High Court, District Courts, and NCLT."
          action={
            <Button variant="secondary" size="sm" onClick={() => alert("CSV Export generated.")}>
              Export Report
            </Button>
          }
        />

        <Table headers={["Jurisdiction / Court", "Total Filings", "Avg Days to Listing", "Orders Downloaded", "Status"]}>
          <Table.Row>
            <Table.Cell style={{ fontWeight: 600 }}>Delhi High Court</Table.Cell>
            <Table.Cell>12</Table.Cell>
            <Table.Cell>4.2 Days</Table.Cell>
            <Table.Cell>48 Orders</Table.Cell>
            <Table.Cell><Badge variant="success">Active Sync</Badge></Table.Cell>
          </Table.Row>
          <Table.Row>
            <Table.Cell style={{ fontWeight: 600 }}>Patiala House District Court</Table.Cell>
            <Table.Cell>8</Table.Cell>
            <Table.Cell>7.1 Days</Table.Cell>
            <Table.Cell>22 Orders</Table.Cell>
            <Table.Cell><Badge variant="success">Active Sync</Badge></Table.Cell>
          </Table.Row>
          <Table.Row>
            <Table.Cell style={{ fontWeight: 600 }}>National Company Law Tribunal (NCLT)</Table.Cell>
            <Table.Cell>4</Table.Cell>
            <Table.Cell>12.0 Days</Table.Cell>
            <Table.Cell>14 Orders</Table.Cell>
            <Table.Cell><Badge variant="info">Synced Daily</Badge></Table.Cell>
          </Table.Row>
        </Table>
      </Card>
    </div>
  );
}
