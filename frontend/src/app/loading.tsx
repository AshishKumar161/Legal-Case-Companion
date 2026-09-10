import { Skeleton } from "@/components/ui/Skeleton";

export default function RootLoading() {
  return (
    <div
      style={{
        maxWidth: "1280px",
        margin: "0 auto",
        padding: "24px 20px",
        display: "flex",
        flexDirection: "column",
        gap: "24px",
      }}
      role="status"
      aria-busy="true"
      aria-label="Loading page content..."
    >
      {/* Header skeleton */}
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        <Skeleton variant="text" width="220px" height="28px" />
        <Skeleton variant="text" width="400px" height="16px" />
      </div>

      {/* KPI Cards skeleton */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
          gap: "16px",
        }}
      >
        <Skeleton variant="card" height="110px" count={1} />
        <Skeleton variant="card" height="110px" count={1} />
        <Skeleton variant="card" height="110px" count={1} />
      </div>

      {/* Main content table/card skeleton */}
      <Skeleton variant="card" height="320px" count={1} />
    </div>
  );
}
