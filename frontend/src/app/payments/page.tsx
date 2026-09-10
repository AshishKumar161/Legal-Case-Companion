"use client";

import React, { useState } from "react";
import { useAuth } from "@/providers/AuthProvider";
import { Card, Button, StatusChip, Table, EmptyState, Badge } from "@/components/ui";

interface PaymentRecord {
  id: string;
  reference: string;
  description: string;
  amount: number;
  status: "PAID" | "PENDING" | "REFUNDED" | "FAILED";
  date: string;
  caseReference?: string;
  partyName?: string;
}

export default function PaymentsPage() {
  const { user } = useAuth();
  const isLawyer = user?.role === "LAWYER";

  // Demo payment / billing ledger items for the active session
  const [payments] = useState<PaymentRecord[]>([
    {
      id: "pay-101",
      reference: "TXN-89421-LCC",
      description: "Initial Legal Strategy & Retainer Consultation",
      amount: 2500,
      status: "PAID",
      date: "04 Sep 2026",
      caseReference: "CIV-2026-0941",
      partyName: isLawyer ? "Vikram Sharma" : "Advocate Ananya Roy",
    },
    {
      id: "pay-102",
      reference: "TXN-89422-LCC",
      description: "High Court Written Submission Drafting & Filing Fee",
      amount: 7500,
      status: "PAID",
      date: "01 Sep 2026",
      caseReference: "CIV-2026-0941",
      partyName: isLawyer ? "Vikram Sharma" : "Advocate Ananya Roy",
    },
    {
      id: "pay-103",
      reference: "TXN-89423-LCC",
      description: "Urgent Virtual Chamber Consultation (30 mins)",
      amount: 1500,
      status: "PAID",
      date: "28 Aug 2026",
      caseReference: "COM-2026-1102",
      partyName: isLawyer ? "Rajesh Verma" : "Advocate Rahul Mehta",
    },
  ]);

  const totalAmount = payments
    .filter((p) => p.status === "PAID")
    .reduce((acc, curr) => acc + curr.amount, 0);

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
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              marginBottom: "6px",
            }}
          >
            <h1
              style={{
                fontSize: "var(--font-size-2xl, 24px)",
                fontWeight: 700,
                color: "var(--text-primary, #f8fafc)",
                fontFamily: "var(--font-display, sans-serif)",
                margin: 0,
              }}
            >
              {isLawyer ? "Practice Billing & Fee Ledger" : "Payments & Invoices"}
            </h1>
            <Badge variant="primary">₹ INR</Badge>
          </div>
          <p
            style={{
              fontSize: "var(--font-size-sm, 14px)",
              color: "var(--text-secondary, #94a3b8)",
              margin: 0,
            }}
          >
            {isLawyer
              ? "Track received consultations, matter retainers, and client disbursements with automated tax receipts."
              : "Review all legal consultation fees, matter deposits, and download GST-compliant digital receipts."}
          </p>
        </div>

        <div style={{ display: "flex", gap: "10px" }}>
          <Button
            variant="secondary"
            onClick={() => alert("GST receipts package download initiated.")}
          >
            📥 Download Statement
          </Button>
          {!isLawyer && (
            <Button
              variant="primary"
              onClick={() => alert("Contact counsel or initiate consultation payment.")}
            >
              Make Payment
            </Button>
          )}
        </div>
      </div>

      {/* Summary KPI Cards */}
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
            {isLawyer ? "Total Fees Received" : "Total Legal Spend"}
          </div>
          <div
            style={{
              fontSize: "28px",
              fontWeight: 700,
              color: "var(--text-primary, #f8fafc)",
              fontFamily: "var(--font-display, sans-serif)",
              marginTop: "4px",
            }}
          >
            ₹{totalAmount.toLocaleString("en-IN")}
          </div>
          <div style={{ fontSize: "12px", color: "var(--success, #10B981)", marginTop: "4px" }}>
            ✓ Verified through Banking Network
          </div>
        </Card>

        <Card variant="elevated" padding="md">
          <div style={{ fontSize: "12px", color: "var(--text-muted, #64748b)", textTransform: "uppercase", fontWeight: 600 }}>
            Completed Transactions
          </div>
          <div
            style={{
              fontSize: "28px",
              fontWeight: 700,
              color: "var(--text-primary, #f8fafc)",
              fontFamily: "var(--font-display, sans-serif)",
              marginTop: "4px",
            }}
          >
            {payments.length}
          </div>
          <div style={{ fontSize: "12px", color: "var(--text-secondary, #94a3b8)", marginTop: "4px" }}>
            All payments authoritatively stamped
          </div>
        </Card>

        <Card variant="elevated" padding="md">
          <div style={{ fontSize: "12px", color: "var(--text-muted, #64748b)", textTransform: "uppercase", fontWeight: 600 }}>
            Pending Invoices
          </div>
          <div
            style={{
              fontSize: "28px",
              fontWeight: 700,
              color: "var(--text-primary, #f8fafc)",
              fontFamily: "var(--font-display, sans-serif)",
              marginTop: "4px",
            }}
          >
            ₹0
          </div>
          <div style={{ fontSize: "12px", color: "var(--success, #10B981)", marginTop: "4px" }}>
            Zero outstanding balance
          </div>
        </Card>
      </div>

      {/* Transactions Table */}
      <Card variant="default" padding="lg">
        <Card.Header
          title="Payment History & Stamped Receipts"
          subtitle="All transactions comply with Reserve Bank of India payment guidelines."
        />

        {payments.length === 0 ? (
          <EmptyState
            icon="💳"
            title="No payment history yet"
            description="When consultations or matter fees are settled, official receipts will be permanently recorded here."
          />
        ) : (
          <Table headers={["Date", "Transaction Ref", "Description", isLawyer ? "Client" : "Counsel", "Amount", "Status", "Receipt"]}>
            {payments.map((p) => (
              <Table.Row key={p.id}>
                <Table.Cell style={{ whiteSpace: "nowrap", color: "var(--text-secondary, #94a3b8)" }}>
                  {p.date}
                </Table.Cell>
                <Table.Cell style={{ fontFamily: "var(--font-mono, monospace)", fontSize: "12px" }}>
                  {p.reference}
                </Table.Cell>
                <Table.Cell>
                  <div style={{ fontWeight: 500 }}>{p.description}</div>
                  {p.caseReference && (
                    <div style={{ fontSize: "11px", color: "var(--text-muted, #64748b)" }}>
                      Matter Ref: {p.caseReference}
                    </div>
                  )}
                </Table.Cell>
                <Table.Cell style={{ whiteSpace: "nowrap" }}>{p.partyName}</Table.Cell>
                <Table.Cell style={{ fontWeight: 700, fontFamily: "var(--font-mono, monospace)" }}>
                  ₹{p.amount.toLocaleString("en-IN")}
                </Table.Cell>
                <Table.Cell>
                  <StatusChip status={p.status} />
                </Table.Cell>
                <Table.Cell>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => alert(`Receipt #${p.reference} generated.`)}
                  >
                    📄 PDF
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
