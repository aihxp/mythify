import { z } from "zod";
import {
  MEMORY_CATEGORIES,
  MEMORY_CLEAR_MCP_REFUSAL,
  MEMORY_DEFAULT_CATEGORY,
} from "./operation-registry.js";

export const MEMORY_TOOL_NAMES = [
  "memory_store",
  "memory_recall",
  "memory_clear",
  "lesson_record",
  "lesson_recall",
];

function requireDep(deps, name) {
  const value = deps[name];
  if (typeof value !== "function") {
    throw new Error(`registerMemoryTools requires deps.${name}`);
  }
  return value;
}

export function registerMemoryTools(server, deps) {
  const guarded = requireDep(deps, "guarded");
  const isoNow = requireDep(deps, "isoNow");
  const loadMemory = requireDep(deps, "loadMemory");
  const saveMemory = requireDep(deps, "saveMemory");
  const recordLesson = requireDep(deps, "recordLesson");
  const readLessonsFrom = requireDep(deps, "readLessonsFrom");
  const projectLessonsDir = requireDep(deps, "projectLessonsDir");
  const globalLessonsDir = requireDep(deps, "globalLessonsDir");

  server.registerTool(
    "memory_store",
    {
      title: "Store a memory entry",
      description:
        "Store or update a key-value memory entry in the project's persistent .mythify state. " +
        "Keys are unique: storing an existing key overwrites it. " +
        "Use this to persist facts, decisions, discoveries, or task state that must survive beyond the current context window, especially on long or multi-session tasks.",
      inputSchema: {
        key: z.string().describe("Unique key for the entry; storing an existing key overwrites it."),
        value: z.string().describe("The content to remember."),
        category: z
          .enum(MEMORY_CATEGORIES)
          .default(MEMORY_DEFAULT_CATEGORY)
          .describe("Entry category: fact, decision, discovery, or state. Defaults to fact."),
      },
    },
    guarded(({ key, value, category }) => {
      const data = loadMemory();
      const existing = data.entries.find((e) => e.key === key);
      const entry = { key, value, category, timestamp: isoNow() };
      if (existing) {
        const idx = data.entries.indexOf(existing);
        data.entries[idx] = entry;
      } else {
        data.entries.push(entry);
      }
      saveMemory(data);
      const verb = existing ? "Updated" : "Stored";
      return `[OK] ${verb} memory entry "${key}" (category: ${category}). Total entries: ${data.entries.length}.`;
    })
  );

  server.registerTool(
    "memory_recall",
    {
      title: "Recall memory entries",
      description:
        "Search the project's persistent memory with a case-insensitive substring match over keys and values, optionally filtered by category. " +
        "Use this at session start and before making decisions, to recover facts, decisions, discoveries, and task state recorded earlier.",
      inputSchema: {
        query: z
          .string()
          .optional()
          .describe("Case-insensitive substring matched against keys and values. Omit to list every entry."),
        category: z
          .enum([...MEMORY_CATEGORIES, "all"])
          .optional()
          .describe("Restrict results to one category, or 'all' for no filter."),
      },
    },
    guarded(({ query, category }) => {
      const data = loadMemory();
      if (data.entries.length === 0) {
        return "[OK] No memory entries yet.";
      }
      const q = (query || "").toLowerCase();
      const matches = data.entries.filter((e) => {
        if (category && category !== "all" && e.category !== category) {
          return false;
        }
        if (q === "") {
          return true;
        }
        return (
          String(e.key).toLowerCase().includes(q) ||
          String(e.value).toLowerCase().includes(q)
        );
      });
      if (matches.length === 0) {
        return "[OK] No memory entries match the given query.";
      }
      const lines = matches.map((e) => `- [${e.category}] ${e.key}: ${e.value}`);
      return `[OK] ${matches.length} memory ${matches.length === 1 ? "entry" : "entries"}:\n${lines.join("\n")}`;
    })
  );

  server.registerTool(
    "memory_clear",
    {
      title: "Clear memory entries",
      description:
        "Remove one memory entry by key, or wipe all entries when confirm_clear_all is true. " +
        "Use this to retire stale or incorrect memories. Calling it with no key and without confirm_clear_all is refused as a safety guard.",
      inputSchema: {
        key: z.string().optional().describe("Key of the single entry to remove."),
        confirm_clear_all: z
          .boolean()
          .optional()
          .describe("Set true to confirm clearing every memory entry. Ignored when key is given."),
      },
    },
    guarded(({ key, confirm_clear_all }) => {
      const data = loadMemory();
      if (key !== undefined && key !== null && key !== "") {
        const idx = data.entries.findIndex((e) => e.key === key);
        if (idx === -1) {
          return `[FAIL] No memory entry with key "${key}". Nothing was cleared.`;
        }
        data.entries.splice(idx, 1);
        saveMemory(data);
        return `[OK] Removed memory entry "${key}". Remaining entries: ${data.entries.length}.`;
      }
      if (confirm_clear_all === true) {
        const count = data.entries.length;
        data.entries = [];
        saveMemory(data);
        return `[OK] Cleared all memory entries (${count} removed).`;
      }
      return MEMORY_CLEAR_MCP_REFUSAL;
    })
  );

  server.registerTool(
    "lesson_record",
    {
      title: "Record a lesson",
      description:
        "Record a durable lesson learned, either in the project store or the cross-project global store. " +
        "Use this after a surprising failure, a non-obvious fix, or a reusable insight, so the lesson survives beyond this session and this project.",
      inputSchema: {
        title: z.string().describe("Short lesson title; it becomes the basis of the lesson filename."),
        detail: z.string().describe("Full lesson detail: what happened, why, and what to do next time."),
        tags: z.array(z.string()).optional().describe("Optional tags for later filtering."),
        scope: z
          .enum(["project", "global"])
          .default("project")
          .describe("project stores under the workspace .mythify; global stores under ~/.mythify for every project."),
      },
    },
    guarded(({ title, detail, tags, scope }) => {
      const fileName = recordLesson(title, detail, tags || [], scope);
      return `[OK] Recorded ${scope} lesson "${title}" (${fileName}).`;
    })
  );

  server.registerTool(
    "lesson_recall",
    {
      title: "Recall recorded lessons",
      description:
        "List recorded lessons from the project store, the global store, or both, optionally filtered by tag. " +
        "Use this at session start and before architectural or risky decisions, to apply lessons learned from earlier work.",
      inputSchema: {
        tag: z.string().optional().describe("Only return lessons carrying this exact tag."),
        scope: z
          .enum(["project", "global", "all"])
          .default("all")
          .describe("Which store to read: project, global, or all. Defaults to all."),
      },
    },
    guarded(({ tag, scope }) => {
      let lessons = [];
      if (scope === "project" || scope === "all") {
        lessons = lessons.concat(readLessonsFrom(projectLessonsDir(), "project"));
      }
      if (scope === "global" || scope === "all") {
        lessons = lessons.concat(readLessonsFrom(globalLessonsDir(), "global"));
      }
      if (lessons.length === 0) {
        return "[OK] No lessons recorded yet.";
      }
      if (tag) {
        lessons = lessons.filter(({ lesson }) => Array.isArray(lesson.tags) && lesson.tags.includes(tag));
        if (lessons.length === 0) {
          return `[OK] No lessons carry the tag "${tag}".`;
        }
      }
      const lines = lessons.map(({ scope: s, lesson }) => {
        let line = `- (${s}) ${lesson.title}: ${lesson.detail}`;
        if (Array.isArray(lesson.tags) && lesson.tags.length > 0) {
          line += ` [tags: ${lesson.tags.join(", ")}]`;
        }
        return line;
      });
      return `[OK] ${lessons.length} ${lessons.length === 1 ? "lesson" : "lessons"}:\n${lines.join("\n")}`;
    })
  );
}
