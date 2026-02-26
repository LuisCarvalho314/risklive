import { describe, expect, it } from "vitest";

import { normalizeToNewsmapTree } from "@/lib/treemap/normalize";
import { sampleDashboard } from "@/tests/fixtures/dashboard";

describe("normalizeToNewsmapTree", () => {
  it("produces root/category/topic/leaf hierarchy", () => {
    const tree = normalizeToNewsmapTree(sampleDashboard.newsmap);
    expect(tree.id).toBe("root::newsmap");
    expect(tree.children?.length).toBeGreaterThan(0);
    const category = tree.children?.[0];
    expect(category?.id?.startsWith("cat::")).toBe(true);
    const topic = category?.children?.[0];
    expect(topic?.id?.startsWith("topic::")).toBe(true);
    const leaf = topic?.children?.[0];
    expect(leaf?.id?.startsWith("leaf::")).toBe(true);
    expect(typeof leaf?.value).toBe("number");
  });

  it("filters out green leaves", () => {
    const greenInput = {
      ...sampleDashboard.newsmap,
      children: [
        {
          name: "category",
          children: [
            {
              name: "Green Item",
              value: 1,
              meta: { title: "Green Item", alertFlag: "Green", category: "category" }
            }
          ]
        }
      ]
    };
    const tree = normalizeToNewsmapTree(greenInput);
    expect(tree.children).toEqual([]);
  });

  it("ensures unique leaf ids even for duplicate source rows", () => {
    const duplicated = {
      ...sampleDashboard.newsmap,
      children: [
        {
          name: "category",
          children: [
            {
              name: "Topic A",
              children: [
                {
                  name: "Dup",
                  value: 1,
                  meta: {
                    title: "Dup",
                    url: "https://example.com/a",
                    alertFlag: "Red",
                    category: "category",
                    topic: "Topic A"
                  }
                },
                {
                  name: "Dup",
                  value: 1,
                  meta: {
                    title: "Dup",
                    url: "https://example.com/a",
                    alertFlag: "Red",
                    category: "category",
                    topic: "Topic A"
                  }
                }
              ]
            }
          ]
        }
      ]
    };

    const tree = normalizeToNewsmapTree(duplicated);
    const leaves = tree.children?.[0]?.children?.[0]?.children ?? [];
    const ids = leaves.map((leaf) => leaf.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
