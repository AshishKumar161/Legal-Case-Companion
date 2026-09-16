"use client";

import React, { useState } from "react";
import { Card, Button, StatusChip, Table, Avatar, EmptyState } from "@/components/ui";

interface ClientRecord {
  id: string;
  name: string;
  email: string;
  phone: string;
  activeMattersCount: number;
  primaryMatter: string;
  status: "ACTIVE" | "PENDING_INTAKE" | "CONCLUDED";
  city: string;
}

export default function ClientsPage() {
  const [clients] = useState<ClientRecord[]>([
    {
      id: "cli-1",
      name: "Vikram Sharma",
      email: "client@lcc.test",
      phone: "+91 98765 43210",
      activeMattersCount: 1,
      primaryMatter: "Sharma v. Delhi Development Authority",
      status: "ACTIVE",
      city: "New Delhi",
    },
    {
      id: "cli-2",
      name: "Rajesh Verma",
      email: "rajesh.verma@example.com",
      phone: "+91 98111 22334",
      activeMattersCount: 1,
      primaryMatter: "Verma Commercial Recovery Suit",
      status: "ACTIVE",
      city: "Gurugram",
    },
    {
      id: "cli-3",
      name: "Meera Krishnan",
      email: "meera.k@example.com",
      phone: "+91 97444 55667",
      activeMattersCount: 0,
      primaryMatter: "Draft Agreement Advisory",
      status: "CONCLUDED",
      city: "Noida",
    },
  ]);

  return (
    <div style={{ maxWidth: "1280px", margin: "0 auto", padding: "24px 20px" }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          flexWrap: "wrap",
          gap: "16px",
          marginBottom: "24px",
        }}
      >
        <div>
          <h1
            style={{
              fontSize: "var(--font-size-2xl, 24px)",
              fontWeight: 700,
              color: "var(--text-primary, #0f172a)",
              fontFamily: "var(--font-display, sans-serif)",
              margin: "0 0 6px 0",
            }}
          >
            Client Directory & Retainers
          </h1>
          <p style={{ fontSize: "var(--font-size-sm, 14px)", color: "var(--text-secondary, #475569)", margin: 0 }}>
            Manage active client rosters, vakalatnama authorizations, and direct matter communications.
          </p>
        </div>

        <Button variant="primary" onClick={() => alert("Client onboarding link created.")}>
          + Invite Client
        </Button>
      </div>

      {/* Summary Row */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: "16px",
          marginBottom: "24px",
        }}
      >
        <Card variant="elevated" padding="md">
          <div style={{ fontSize: "12px", color: "var(--text-muted, #64748b)", textTransform: "uppercase", fontWeight: 600 }}>
            Total Litigants
          </div>
          <div style={{ fontSize: "28px", fontWeight: 700, marginTop: "4px" }}>
            {clients.length}
          </div>
          <div style={{ fontSize: "12px", color: "var(--success, #10B981)", marginTop: "4px" }}>
            Verified Contact & KYC
          </div>
        </Card>

        <Card variant="elevated" padding="md">
          <div style={{ fontSize: "12px", color: "var(--text-muted, #64748b)", textTransform: "uppercase", fontWeight: 600 }}>
            Active Matters Represented
          </div>
          <div style={{ fontSize: "28px", fontWeight: 700, marginTop: "4px" }}>
            {clients.reduce((sum, c) => sum + c.activeMattersCount, 0)}
          </div>
          <div style={{ fontSize: "12px", color: "var(--info, #06B6D4)", marginTop: "4px" }}>
            Vakalatnama Stamped & Filed
          </div>
        </Card>
      </div>

      {/* Clients Table */}
      <Card variant="default" padding="lg">
        <Card.Header
          title="Litigant Registry"
          subtitle="Directory of litigants represented before judicial and arbitral forums."
        />

        {clients.length === 0 ? (
          <EmptyState
            icon="👥"
            title="No clients on record yet"
            description="When you accept consultation requests or create new matter workspaces, your clients will be recorded here."
          />
        ) : (
          <Table headers={["Client Name", "Contact", "Location", "Primary Matter", "Active Cases", "Status", "Actions"]}>
            {clients.map((c) => (
              <Table.Row key={c.id}>
                <Table.Cell>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <Avatar name={c.name} roleBadge="client" size="sm" />
                    <div>
                      <div style={{ fontWeight: 600 }}>{c.name}</div>
                      <div style={{ fontSize: "11px", color: "var(--text-muted, #64748b)" }}>{c.email}</div>
                    </div>
                  </div>
                </Table.Cell>
                <Table.Cell style={{ fontFamily: "var(--font-mono, monospace)", fontSize: "12px" }}>
                  {c.phone}
                </Table.Cell>
                <Table.Cell>{c.city}</Table.Cell>
                <Table.Cell style={{ maxWidth: "260px" }}>
                  <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {c.primaryMatter}
                  </div>
                </Table.Cell>
                <Table.Cell style={{ fontWeight: 600 }}>
                  {c.activeMattersCount}
                </Table.Cell>
                <Table.Cell>
                  <StatusChip status={c.status} />
                </Table.Cell>
                <Table.Cell>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => alert(`Opening client dossier for ${c.name}`)}
                  >
                    View File
                  </Button>
                </Table.Cell>
              </Table.Row>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
