import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  ConfidenceBadge,
  DetectionIndicator,
  EvidenceConfidence,
  JobStatusBadge,
  ScoreBadge,
} from "./badges";

describe("badges", () => {
  it("JobStatusBadge renders human label", () => {
    render(<JobStatusBadge status="COMPLETED_WITH_WARNINGS" />);
    expect(screen.getByText("completed with warnings")).toBeInTheDocument();
  });

  it("ConfidenceBadge tolerates undefined", () => {
    render(<ConfidenceBadge confidence={undefined} />);
    expect(screen.getByText("not enough evidence")).toBeInTheDocument();
  });

  it("ScoreBadge shows dash for null", () => {
    render(<ScoreBadge score={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("ScoreBadge renders the number", () => {
    render(<ScoreBadge score={87} />);
    expect(screen.getByText("87")).toBeInTheDocument();
  });

  it("EvidenceConfidence maps 0.9 to high", () => {
    render(<EvidenceConfidence value={0.9} />);
    expect(screen.getByText(/high · 0.90/)).toBeInTheDocument();
  });

  it("DetectionIndicator distinguishes not-detected from unknown", () => {
    const { rerender } = render(<DetectionIndicator state={false} label="Booking" />);
    expect(screen.getByText("— Not detected")).toBeInTheDocument();
    rerender(<DetectionIndicator state={null} label="Booking" />);
    expect(screen.getByText("? Unknown")).toBeInTheDocument();
    rerender(<DetectionIndicator state={true} label="Booking" />);
    expect(screen.getByText("✓ Found")).toBeInTheDocument();
  });
});
