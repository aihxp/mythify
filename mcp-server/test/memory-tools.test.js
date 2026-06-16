import test from "node:test";
import assert from "node:assert/strict";
import {
  MEMORY_TOOL_NAMES,
  registerMemoryTools,
} from "../src/memory-tools.js";

test("memory tool registrar wires memory and lesson handlers", async () => {
  const registered = [];
  let memory = { entries: [] };
  const lessons = [];
  const server = {
    registerTool(name, config, handler) {
      registered.push({ name, config, handler });
    },
  };

  registerMemoryTools(server, {
    guarded: (handler) => async (args) => handler(args || {}),
    isoNow: () => "2026-06-16T00:00:00.000Z",
    loadMemory: () => memory,
    saveMemory: (data) => {
      memory = data;
    },
    recordLesson: (title, detail, tags, scope) => {
      lessons.push({ scope, lesson: { title, detail, tags } });
      return `${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.json`;
    },
    readLessonsFrom: (_dir, scope) => lessons.filter((entry) => entry.scope === scope),
    projectLessonsDir: () => "/tmp/mythify-project-lessons",
    globalLessonsDir: () => "/tmp/mythify-global-lessons",
  });

  assert.deepEqual(registered.map((entry) => entry.name), MEMORY_TOOL_NAMES);
  const memoryStore = registered.find((entry) => entry.name === "memory_store");
  assert.ok(memoryStore.config.inputSchema.category);

  const storeResult = await memoryStore.handler({
    key: "decision",
    value: "ship smaller slices",
    category: "decision",
  });
  assert.match(storeResult, /^\[OK\] Stored memory entry/);
  assert.equal(memory.entries[0].key, "decision");

  const memoryRecall = registered.find((entry) => entry.name === "memory_recall");
  const recallResult = await memoryRecall.handler({ query: "smaller" });
  assert.match(recallResult, /ship smaller slices/);

  const lessonRecord = registered.find((entry) => entry.name === "lesson_record");
  const lessonResult = await lessonRecord.handler({
    title: "Small Slices",
    detail: "Move one group at a time.",
    tags: ["quality"],
    scope: "project",
  });
  assert.match(lessonResult, /^\[OK\] Recorded project lesson/);

  const lessonRecall = registered.find((entry) => entry.name === "lesson_recall");
  const lessonList = await lessonRecall.handler({ tag: "quality", scope: "project" });
  assert.match(lessonList, /Small Slices/);
});

test("memory tool registrar rejects missing required deps", () => {
  assert.throws(
    () => registerMemoryTools({ registerTool() {} }, {}),
    /requires deps\.guarded/
  );
});
