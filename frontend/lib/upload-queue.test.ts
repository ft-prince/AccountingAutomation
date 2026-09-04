import { describe, expect, test } from "vitest";
import { createUploadQueue, type UploadTask } from "./upload-queue";

function fakeFile(name: string): File {
  return new File(["x"], name, { type: "application/pdf" });
}

describe("createUploadQueue", () => {
  test("never has more than 4 uploads in flight with 200 files enqueued", async () => {
    // Arrange
    let inFlight = 0;
    let peakInFlight = 0;
    const pending: (() => void)[] = [];
    let latest: readonly UploadTask[] = [];
    const queue = createUploadQueue({
      concurrency: 4,
      upload: () =>
        new Promise((resolve) => {
          inFlight += 1;
          peakInFlight = Math.max(peakInFlight, inFlight);
          pending.push(() => {
            inFlight -= 1;
            resolve({ documentId: `doc-${pending.length}`, status: "pending" });
          });
        }),
      onChange: (tasks) => {
        latest = tasks;
      },
    });

    // Act
    queue.add(Array.from({ length: 200 }, (_, index) => fakeFile(`invoice-${index}.pdf`)));

    // Assert — only 4 started, 196 waiting
    expect(latest.filter((task) => task.status === "uploading")).toHaveLength(4);
    expect(latest.filter((task) => task.status === "queued")).toHaveLength(196);

    // Drain: resolve one at a time; the queue must refill to exactly 4 each time.
    while (pending.length > 0) {
      const finish = pending.shift();
      finish?.();
      await Promise.resolve();
      await Promise.resolve();
      expect(inFlight).toBeLessThanOrEqual(4);
    }
    expect(peakInFlight).toBe(4);
    expect(latest.every((task) => task.status === "processing")).toBe(true);
  });

  test("a rejected upload becomes failed and retry re-queues it", async () => {
    let attempts = 0;
    let latest: readonly UploadTask[] = [];
    const queue = createUploadQueue({
      concurrency: 1,
      upload: async () => {
        attempts += 1;
        if (attempts === 1) throw new Error("network");
        return { documentId: "doc-1", duplicateOf: "doc-0" };
      },
      onChange: (tasks) => {
        latest = tasks;
      },
    });
    queue.add([fakeFile("a.pdf")]);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(latest[0]).toMatchObject({ status: "failed", error: "network" });

    queue.retry(latest[0].id);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(latest[0]).toMatchObject({ status: "duplicate", duplicateOf: "doc-0" });
  });
});
