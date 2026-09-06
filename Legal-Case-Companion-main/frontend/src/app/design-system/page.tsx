"use client";

import React, { useState } from "react";
import {
  Button,
  Input,
  Select,
  Textarea,
  Checkbox,
  Radio,
  Badge,
  StatusChip,
  Card,
  Modal,
  Drawer,
  Tabs,
  Alert,
  Tooltip,
  Breadcrumb,
  Pagination,
  Table,
  Skeleton,
  EmptyState,
  ErrorState,
  Avatar,
  TimelineItem,
} from "@/components/ui";
import { LegalTerm } from "@/components/LegalTerm";

export default function DesignSystemShowcasePage() {
  const [modalOpen, setModalOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("tab1");
  const [checkboxVal, setCheckboxVal] = useState(true);
  const [radioVal, setRadioVal] = useState("opt1");
  const [page, setPage] = useState(1);

  return (
    <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "32px 20px", display: "flex", flexDirection: "column", gap: "36px" }}>
      {/* Page Title */}
      <div>
        <Breadcrumb
          items={[
            { label: "Home", href: "/dashboard" },
            { label: "Design System Foundation" },
          ]}
        />
        <h1 style={{ fontSize: "28px", fontWeight: 700, marginTop: "12px", fontFamily: "var(--font-display, sans-serif)" }}>
          LCC Canonical Design System — Component Foundation (Phase 7.1)
        </h1>
        <p style={{ color: "var(--text-secondary, #94a3b8)", fontSize: "14px", margin: "4px 0 0 0" }}>
          WCAG 2.2 AA compliant tokens, opaque elevated surfaces, ≥44px touch targets, and Indian legal primitives.
        </p>
      </div>

      {/* SECTION 1: Buttons & Interactive Elements */}
      <Card variant="default" padding="lg">
        <Card.Header title="1. Buttons & Touch Targets (≥44px)" subtitle="Semantic variants with loading and disabled states" />
        <div style={{ display: "flex", flexWrap: "wrap", gap: "12px", alignItems: "center" }}>
          <Button variant="primary" id="btn-primary">Primary Action</Button>
          <Button variant="secondary" id="btn-secondary">Secondary Action</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">Danger / Urgent</Button>
          <Button variant="success">Success / Verified</Button>
          <Button variant="primary" isLoading>Loading State</Button>
          <Button variant="secondary" disabled>Disabled State</Button>
        </div>
      </Card>

      {/* SECTION 2: Form Controls */}
      <Card variant="default" padding="lg">
        <Card.Header title="2. Form Controls & Validation" subtitle="Accessible labels, descriptions, and error states" />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "20px" }}>
          <Input label="Case Title or CNR Number" placeholder="e.g. DLHC010023452026" helperText="16-character alphanumeric reference" required id="input-cnr" />
          <Input label="Disputed Amount" placeholder="₹ Enter claim value" error="Statutory court fee must be calculated for claims exceeding ₹5,00,000." id="input-error" />
          <Select
            label="Court Jurisdiction"
            options={[
              { value: "dlhc", label: "Delhi High Court" },
              { value: "phdc", label: "Patiala House District Court" },
              { value: "nclt", label: "National Company Law Tribunal" },
            ]}
            id="select-court"
          />
          <Textarea label="Brief Facts of the Dispute" placeholder="Summary of cause of action..." rows={3} id="textarea-facts" />
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: "24px", marginTop: "16px" }}>
          <Checkbox
            label="I confirm all evidentiary documents are authentic"
            description="Verified under solemn affirmation per Section 193 Indian Penal Code."
            checked={checkboxVal}
            onChange={(e) => setCheckboxVal(e.target.checked)}
            id="checkbox-affirmation"
          />
          <div style={{ display: "flex", gap: "16px" }}>
            <Radio
              name="dispute-type"
              label="Civil Suit"
              checked={radioVal === "opt1"}
              onChange={() => setRadioVal("opt1")}
              id="radio-civil"
            />
            <Radio
              name="dispute-type"
              label="Commercial Dispute"
              checked={radioVal === "opt2"}
              onChange={() => setRadioVal("opt2")}
              id="radio-comm"
            />
          </div>
        </div>
      </Card>

      {/* SECTION 3: Badges & Status Chips */}
      <Card variant="default" padding="lg">
        <Card.Header title="3. Badges & Legal Status Chips" subtitle="Semantic status tokens with high contrast" />
        <div style={{ display: "flex", flexWrap: "wrap", gap: "10px", alignItems: "center" }}>
          <StatusChip status="OPEN" pulse />
          <StatusChip status="IN_PROGRESS" />
          <StatusChip status="PENDING_COURT" />
          <StatusChip status="JUDGMENT_RESERVED" />
          <StatusChip status="STATUTORY_LIMITATION" pulse />
          <StatusChip status="HEARING_SCHEDULED" />
          <StatusChip status="VERIFIED" />
          <StatusChip status="DISPOSED" />
          <Badge variant="primary" dot>Brand Pill</Badge>
          <Badge variant="urgent">Urgent</Badge>
          <Badge variant="warning">Limitation Warning</Badge>
          <Badge variant="info">Order Synced</Badge>
        </div>
      </Card>

      {/* SECTION 4: LegalTerm Component */}
      <Card variant="default" padding="lg">
        <Card.Header
          title="4. LegalTerm Plain-Language Component (Section 6)"
          subtitle="Three information layers: 1) Plain explanation, 2) Technical term, 3) Provenance/source. Compact default."
        />
        <div style={{ display: "flex", flexDirection: "column", gap: "14px", fontSize: "14px", lineHeight: 1.6 }}>
          <p>
            Your property title suit has reached the concluding stage:{" "}
            <LegalTerm term="judgment reserved" source="Delhi High Court · Single Bench" id="legalterm-judgment" />.
          </p>
          <p>
            The registry has published the official listing:{" "}
            <LegalTerm term="cause list" source="eCourts High Court Listing Board" />.
          </p>
          <p>
            Your counsel has prepared the statutory authorization:{" "}
            <LegalTerm term="vakalatnama" source="Bar Council of Delhi Rules" />.
          </p>
        </div>
      </Card>

      {/* SECTION 5: Tabs, Table, and Pagination */}
      <Card variant="default" padding="lg">
        <Card.Header title="5. Tabs, Responsive Tables & Pagination" subtitle="Structured data representation" />
        <Tabs
          tabs={[
            { id: "tab1", label: "Active Listings", badge: 3 },
            { id: "tab2", label: "Orders & Judgments", badge: 12 },
            { id: "tab3", label: "Limitation Deadlines", badge: 1 },
          ]}
          activeTab={activeTab}
          onChange={setActiveTab}
        />

        <div style={{ marginTop: "16px" }}>
          <Table headers={["Item No.", "Forum", "Matter Title", "Status", "Action"]}>
            <Table.Row>
              <Table.Cell style={{ fontFamily: "var(--font-mono, monospace)" }}>Item #14</Table.Cell>
              <Table.Cell>Court Room 21, Delhi HC</Table.Cell>
              <Table.Cell style={{ fontWeight: 600 }}>Sharma v. Municipal Corporation of Delhi</Table.Cell>
              <Table.Cell><StatusChip status="HEARING_SCHEDULED" /></Table.Cell>
              <Table.Cell><Button size="sm" variant="secondary">View Listing</Button></Table.Cell>
            </Table.Row>
            <Table.Row>
              <Table.Cell style={{ fontFamily: "var(--font-mono, monospace)" }}>Item #03</Table.Cell>
              <Table.Cell>Court Room 04, Patiala House</Table.Cell>
              <Table.Cell style={{ fontWeight: 600 }}>Verma Commercial Recovery Matter</Table.Cell>
              <Table.Cell><StatusChip status="JUDGMENT_RESERVED" /></Table.Cell>
              <Table.Cell><Button size="sm" variant="secondary">View Order</Button></Table.Cell>
            </Table.Row>
          </Table>
        </div>

        <Pagination currentPage={page} totalPages={4} onPageChange={setPage} />
      </Card>

      {/* SECTION 6: Modals, Drawers & Overlays */}
      <Card variant="default" padding="lg">
        <Card.Header title="6. Dialogs & Overlays" subtitle="Accessible modal and slide-over drawer with Escape and backdrop close" />
        <div style={{ display: "flex", gap: "12px" }}>
          <Button variant="primary" onClick={() => setModalOpen(true)} id="btn-open-modal">Open Accessible Modal</Button>
          <Button variant="secondary" onClick={() => setDrawerOpen(true)} id="btn-open-drawer">Open Slide Drawer</Button>
          <Tooltip content="Permanent 16-character case identifier across Indian eCourts">
            <Button variant="outline">Hover or Focus for Tooltip</Button>
          </Tooltip>
        </div>

        <Modal
          isOpen={modalOpen}
          onClose={() => setModalOpen(false)}
          title="Case Filing Verification"
          description="Please review statutory details before submitting to the court registry."
          footer={
            <>
              <Button variant="ghost" onClick={() => setModalOpen(false)}>Cancel</Button>
              <Button variant="primary" onClick={() => setModalOpen(false)}>Confirm Filing</Button>
            </>
          }
        >
          <p style={{ fontSize: "14px", lineHeight: 1.5, margin: 0 }}>
            This matter will be synchronized with the official eCourts registry. You will receive an SMS and email notification upon CNR generation.
          </p>
        </Modal>

        <Drawer
          isOpen={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          title="Matter Filter Drawer"
          footer={
            <Button variant="primary" style={{ width: "100%" }} onClick={() => setDrawerOpen(false)}>
              Apply Filters
            </Button>
          }
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <Input label="Keyword" placeholder="Search orders..." />
            <Select
              label="Forum"
              options={[
                { value: "all", label: "All Forums" },
                { value: "hc", label: "High Courts" },
                { value: "dc", label: "District Courts" },
              ]}
            />
          </div>
        </Drawer>
      </Card>

      {/* SECTION 7: Feedback, Empty & Error States */}
      <Card variant="default" padding="lg">
        <Card.Header title="7. User Feedback, Empty & Error Experience" subtitle="Human-centered non-technical messaging (Section 20 & 21)" />
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          <Alert variant="info" title="Registry Listing Updated">
            The cause list for Court Room 12 has been released. Your matter is scheduled for 11:30 AM.
          </Alert>

          <Alert variant="urgent" title="Statutory Limitation Notice" onDismiss={() => alert("Dismissed")}>
            Written Statement must be filed within 14 days under Order VIII CPC to prevent forfeiture of defense.
          </Alert>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "20px" }}>
            <EmptyState
              icon="⚖"
              title="You don't have any cases yet."
              description="Create a case to start keeping your legal information in one place."
              actionLabel="Create a case"
              onAction={() => alert("Create case clicked")}
            />

            <ErrorState
              title="Something went wrong while loading this information."
              description="We encountered an issue retrieving the latest court orders. Please try again or return to the main overview."
              onRetry={() => alert("Retry triggered")}
              technicalError="NetworkTimeoutException: eCourts API did not respond within 4000ms"
            />
          </div>
        </div>
      </Card>

      {/* SECTION 8: Avatars, Timeline & Skeletons */}
      <Card variant="default" padding="lg">
        <Card.Header title="8. Avatars, Matter Timeline & Loading Skeletons" subtitle="Actors, procedural history, and progressive loading" />
        <div style={{ display: "flex", gap: "16px", alignItems: "center", marginBottom: "20px" }}>
          <Avatar name="Ananya Roy" roleBadge="lawyer" size="lg" />
          <Avatar name="Vikram Sharma" roleBadge="client" size="md" />
          <Avatar name="Pooja Deshmukh" roleBadge="admin" size="sm" />
          <Avatar name="Unknown User" size="xs" />
        </div>

        <div style={{ marginBottom: "24px" }}>
          <TimelineItem
            title="Written Statement Filed & Stamped"
            description="Defendant submitted formal response refuting claim paragraphs 1 through 14."
            timestamp="04 Sep 2026 · 02:30 PM"
            actor="Advocate Ananya Roy"
            status="IN_PROGRESS"
          />
          <TimelineItem
            title="Court Summons Served on Respondent"
            description="Speed-post delivery confirmed by India Post tracking receipt."
            timestamp="22 Aug 2026 · 11:00 AM"
            actor="Registry Clerk"
            status="VERIFIED"
          />
          <TimelineItem
            title="Initial Plaint Instituted"
            description="Civil suit registered under Order VII CPC."
            timestamp="10 Aug 2026 · 04:15 PM"
            actor="Vikram Sharma"
            status="OPEN"
            isLast
          />
        </div>

        <div>
          <div style={{ fontSize: "12px", color: "var(--text-muted, #64748b)", marginBottom: "8px", textTransform: "uppercase" }}>
            Loading Skeleton Placeholder (aria-busy=&quot;true&quot;)
          </div>
          <Skeleton variant="card" height="90px" count={2} />
        </div>
      </Card>
    </div>
  );
}
