"use client";

import React, { useState } from "react";
import { Card, Button, StatusChip, Table, Avatar, Badge } from "@/components/ui";

interface TeamMember {
  id: string;
  name: string;
  email: string;
  role: "ADMIN" | "LAWYER" | "PARALEGAL" | "RESEARCHER";
  status: "ACTIVE" | "INVITED" | "SUSPENDED";
  casesAssigned: number;
}

export default function AdminUsersPage() {
  const [members] = useState<TeamMember[]>([
    {
      id: "u-1",
      name: "Advocate Ananya Roy",
      email: "advocate@lcc.test",
      role: "LAWYER",
      status: "ACTIVE",
      casesAssigned: 8,
    },
    {
      id: "u-2",
      name: "Platform Administrator",
      email: "admin@lcc.test",
      role: "ADMIN",
      status: "ACTIVE",
      casesAssigned: 0,
    },
    {
      id: "u-3",
      name: "Pooja Deshmukh",
      email: "pooja.d@lcc.test",
      role: "PARALEGAL",
      status: "ACTIVE",
      casesAssigned: 12,
    },
  ]);

  return (
    <div style={{ maxWidth: "1280px", margin: "0 auto", padding: "24px 20px" }}>
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
              color: "var(--text-primary, #f8fafc)",
              fontFamily: "var(--font-display, sans-serif)",
              margin: "0 0 6px 0",
            }}
          >
            Organization Team & Roles
          </h1>
          <p style={{ fontSize: "var(--font-size-sm, 14px)", color: "var(--text-secondary, #94a3b8)", margin: 0 }}>
            Manage advocates, paralegals, and practice managers with granular role-based access control.
          </p>
        </div>

        <Button variant="primary" onClick={() => alert("Invite teammate modal opened.")}>
          + Invite Team Member
        </Button>
      </div>

      <Card variant="default" padding="lg">
        <Table headers={["Member Name", "Email", "Assigned Role", "Active Matters", "Status", "Actions"]}>
          {members.map((m) => (
            <Table.Row key={m.id}>
              <Table.Cell>
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <Avatar name={m.name} size="sm" />
                  <span style={{ fontWeight: 600 }}>{m.name}</span>
                </div>
              </Table.Cell>
              <Table.Cell style={{ color: "var(--text-secondary, #94a3b8)", fontSize: "12px" }}>
                {m.email}
              </Table.Cell>
              <Table.Cell>
                <Badge variant={m.role === "ADMIN" ? "urgent" : m.role === "LAWYER" ? "primary" : "info"}>
                  {m.role}
                </Badge>
              </Table.Cell>
              <Table.Cell style={{ fontWeight: 600 }}>{m.casesAssigned}</Table.Cell>
              <Table.Cell>
                <StatusChip status={m.status} />
              </Table.Cell>
              <Table.Cell>
                <Button variant="ghost" size="sm" onClick={() => alert(`Edit permissions for ${m.name}`)}>
                  Permissions
                </Button>
              </Table.Cell>
            </Table.Row>
          ))}
        </Table>
      </Card>
    </div>
  );
}
