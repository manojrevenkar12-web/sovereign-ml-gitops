import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import data from "../public/data.json";
import { App } from "../src/app/App";

const ok = async () => data;

afterEach(cleanup);

describe("dashboard", () => {
  it("shows a skeleton, then every section", async () => {
    render(<App fetcher={ok} />);
    expect(screen.getByRole("status")).toBeTruthy();
    expect(await screen.findByText("54 releases with known faults, decided three ways")).toBeTruthy();
    expect(screen.getByText("What reaches Loki")).toBeTruthy();
    expect(screen.getByText("No authority reaches another")).toBeTruthy();
    expect(screen.getAllByRole("listitem").length).toBeGreaterThan(2);
  });

  it("switches policy and updates the counts", async () => {
    render(<App fetcher={ok} />);
    await screen.findByText("54 releases with known faults, decided three ways");
    const gate = data.release.policies.gate;
    expect(screen.getByText(`${gate.bad_shipped} of ${gate.bad_total}`)).toBeTruthy();
    fireEvent.click(screen.getByRole("radio", { name: "Always ship" }));
    const always = data.release.policies.always;
    expect(screen.getByText(`${always.bad_shipped} of ${always.bad_total}`)).toBeTruthy();
  });

  it("offers a retry when the data does not load", async () => {
    let calls = 0;
    const flaky = async () => {
      calls += 1;
      if (calls === 1) throw new Error("data.json answered 404");
      return data;
    };
    render(<App fetcher={flaky} />);
    const button = await screen.findByRole("button", { name: "Load again" });
    expect(screen.getByRole("alert").textContent).toContain("404");
    await act(async () => fireEvent.click(button));
    expect(await screen.findByText("What reaches Loki")).toBeTruthy();
  });

  it("says what to run when there are no candidates", async () => {
    const empty = async () => ({ ...data, release: { ...data.release, rows: [] } });
    render(<App fetcher={empty} />);
    expect(await screen.findByText(/No release candidates yet/)).toBeTruthy();
  });
});
