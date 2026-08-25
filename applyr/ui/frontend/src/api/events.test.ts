import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  onmessage: ((event: { data: string }) => void) | null = null;
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  emit(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }

  emitRaw(data: string) {
    this.onmessage?.({ data });
  }
}

beforeEach(() => {
  MockEventSource.instances = [];
  vi.stubGlobal("EventSource", MockEventSource);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const { subscribeToPipelineEvents } = await import("./events");

describe("subscribeToPipelineEvents", () => {
  it("connects to GET /api/events on the API base", () => {
    subscribeToPipelineEvents(vi.fn());
    expect(MockEventSource.instances).toHaveLength(1);
    expect(MockEventSource.instances[0].url).toBe("http://127.0.0.1:8000/api/events");
  });

  it("parses a posted event and forwards it to the callback", () => {
    const onEvent = vi.fn();
    subscribeToPipelineEvents(onEvent);

    MockEventSource.instances[0].emit({ offer_id: 42, stage: "cv", pipeline_stage_at: "2026-08-25T00:00:00Z" });

    expect(onEvent).toHaveBeenCalledExactlyOnceWith({
      offer_id: 42,
      stage: "cv",
      pipeline_stage_at: "2026-08-25T00:00:00Z",
    });
  });

  it("silently drops a malformed payload instead of throwing", () => {
    const onEvent = vi.fn();
    subscribeToPipelineEvents(onEvent);

    expect(() => MockEventSource.instances[0].emitRaw("not json")).not.toThrow();
    expect(onEvent).not.toHaveBeenCalled();
  });

  it("closes the underlying EventSource when unsubscribed", () => {
    const unsubscribe = subscribeToPipelineEvents(vi.fn());
    unsubscribe();
    expect(MockEventSource.instances[0].close).toHaveBeenCalledOnce();
  });
});
