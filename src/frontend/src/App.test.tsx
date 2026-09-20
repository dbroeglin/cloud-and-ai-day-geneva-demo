import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App";

const event = {
  id: "geneva-2026", name: "Cloud & AI Day Geneva", date: "2026-09-21",
  timezone: "Europe/Zurich", venue: "Campus Biotech", notice: "Demo agenda.",
  sessions: [{
    id: "meeting-to-pull-request", title: "From a meeting to a pull request", room: "Auditorium",
    start: "2026-09-21T13:00:00+02:00", end: "2026-09-21T13:45:00+02:00",
    description: "Live demo", sample: false,
  }],
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(event), { status: 200 })));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("event companion baseline", () => {
  it("renders an English agenda without deferred demo features", async () => {
    render(<App />);
    expect(await screen.findByText("From a meeting to a pull request")).toBeDefined();
    expect(screen.queryByText(/export/i)).toBeNull();
    expect(screen.queryByText(/moderation/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /french/i })).toBeNull();
  });

  it("keeps a failed private suggestion draft and shows the error", async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Suggest a feature" }));
    fireEvent.change(screen.getByLabelText("Your idea in a few words"), { target: { value: "Room map" } });
    fireEvent.change(screen.getByLabelText("Tell us a little more"), { target: { value: "Show where rooms are." } });
    vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify({
      error: { message: "Storage is unavailable. Retry later." },
    }), { status: 503 }));
    fireEvent.click(screen.getByRole("button", { name: "Send your idea" }));
    expect(await screen.findByRole("alert")).toBeDefined();
    expect((screen.getByLabelText("Your idea in a few words") as HTMLInputElement).value).toBe("Room map");
    expect(screen.queryByText("Your idea is saved.")).toBeNull();
  });

  it("shows a receipt only after the backend confirms persistence", async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Suggest a feature" }));
    fireEvent.change(screen.getByLabelText("Your idea in a few words"), { target: { value: "Room map" } });
    fireEvent.change(screen.getByLabelText("Tell us a little more"), { target: { value: "Show where rooms are." } });
    vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify({ id: "receipt-123" }), { status: 200 }));
    fireEvent.click(screen.getByRole("button", { name: "Send your idea" }));
    await waitFor(() => expect(screen.getByText("Your idea is saved.")).toBeDefined());
    expect((screen.getByLabelText("Your idea in a few words") as HTMLInputElement).value).toBe("");
  });
});
