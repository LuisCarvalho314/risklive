import { expect, it } from "vitest";
import { buildTreemapFromSecaVerboseTree } from "@/lib/newsmap-experimental";
import { applyExperimentalSizeMetric, experimentalMetricStatus, type ExperimentalSizeMetric } from "@/lib/newsmap-experimental-shared";
import { computeLayout } from "@/lib/treemap/layout";
import { buildWeightedTree } from "@/lib/treemap/focus";
import { defaultTuning } from "@/lib/treemap/config";
import type { TreemapNode } from "@/lib/dashboard";
function fixture(alpha = [0.1, 0.9], variant = 1) {
  return buildTreemapFromSecaVerboseTree({
    hkts: [1,2].map(id => ({ hkt_id: id, parent_node_id: 0 })),
    nodes: [1,2].map(id => ({ node_id: id, hkt_id: id, sources: [] })),
    decision_diagnostics: [1,2].map((id,i) => ({hkt_id:id+10,output_hkt_id:id,should_reconstruct:i===1})),
    display_diagnostics: [1,2].map((id,i) => ({ hkt_id: id,
      mapped_source_count: [50,10][i]*variant, should_reconstruct: i===1,
      alpha_error: 99, beta_error: 99, paper_alpha_error: alpha[i],
      paper_beta_error: [0.8,0.2][i], paper_word_importance_error: [0.3,0.7][i] }))
  }, { activeWindowDays: 30 });
}
const tuning = { ...defaultTuning, weightMode: "value" as const, useLayoutLabelBand: false,
  groupBorderByDepth: { root: 0, category: 0, topic: 0, leaf: 0 },
  groupBorderInnerByDepth: { root: 0, category: 0, topic: 0, leaf: 0 } };
function areas(tree: TreemapNode, metric: ExperimentalSizeMetric, inverse = false) {
  const weighted = applyExperimentalSizeMetric(tree, metric, inverse ? "highToSmall" : "highToLarge");
  const layout = computeLayout(buildWeightedTree(weighted, new Set(), tuning),1000,1000,tuning);
  return [1,2].map(id => { const r=layout.byId.get(`node::${id}`)!; return (r.x1-r.x0)*(r.y1-r.y0); });
}
it("loads actual Option1 fields and RMS without placeholders", () => {
  const m=fixture().children![0].meta!.experimentalMetrics!;
  expect(m).toMatchObject({ mappedSourceCount:50, alphaError:0.1, betaError:0.8, wordImportanceError:0.3, provenance:"seca_actual" });
  expect(m.combinedError).toBeCloseTo(Math.sqrt((0.01+0.64+0.09)/3));
});
it.each(["mappedSourceCount","betaError","alphaError","wordImportanceError","triggeredScore"] as const)("%s produces different areas and reverses ordering", metric => {
  const [a,b]=areas(fixture(),metric), [ai,bi]=areas(fixture(),metric,true);
  expect(a).not.toBe(b); expect((a-b)*(ai-bi)).toBeLessThan(0);
});
it("changes rankings between mapped sources and alpha", () => {
  const [a,b]=areas(fixture(),"mappedSourceCount"), [c,d]=areas(fixture(),"alphaError");
  expect(a).toBeGreaterThan(b); expect(c).toBeLessThan(d);
});
it("preserves zero and small errors", () => {
  const [a,b]=areas(fixture([0,0.0002]),"alphaError"); expect(a).toBeGreaterThan(0); expect(b).toBeGreaterThan(a);
  const [c,d]=areas(fixture([0.0002,0.0007]),"alphaError"); expect(d/c).toBeCloseTo(3.5,4);
});
it("exposes unavailable legacy metrics and keeps Composite explicit", () => {
  const tree=fixture(); tree.children!.forEach((n,i) => { n.meta!.experimentalMetrics={hktId:i+1,composite:i===0?10:2}; });
  expect(experimentalMetricStatus(tree,"alphaError").unavailable).toBe(true);
  const [a,b]=areas(tree,"alphaError"); expect(a).toBeCloseTo(b);
  const [c,d]=areas(tree,"composite"); expect(c).toBeGreaterThan(d);
  expect(applyExperimentalSizeMetric(tree,"alphaError").meta?.experimentalMetricProvenance).toBe("unavailable");
  expect(applyExperimentalSizeMetric(tree,"composite").meta?.experimentalMetricProvenance).toBe("legacy_proxy");
});
it("does not multiply HKT budget by descendants", () => {
  const tree=fixture(), first=tree.children![0];
  first.children=[1,2,3].map(i => ({id:`nested${i}`,name:"child",meta:first.meta}));
  const [a,b]=areas(tree,"alphaError"); expect(b/a).toBeCloseTo(9,5);
  expect(computeLayout(applyExperimentalSizeMetric(tree,"alphaError"),1000,1000,tuning).byId.get("root::newsmap")?.value).toBeCloseTo(1);
});
it("uses each snapshot and variant's own diagnostics", () => {
  const old=fixture([0.8,0.2]), next=fixture([0.2,0.8]);
  expect(areas(old,"alphaError")[0]).toBeGreaterThan(areas(old,"alphaError")[1]);
  expect(areas(next,"alphaError")[0]).toBeLessThan(areas(next,"alphaError")[1]);
  for(const v of [3,7,30]) expect(fixture(undefined,v).children![0].meta!.experimentalMetrics!.mappedSourceCount).toBe(50*v);
});

it("keeps partial availability local and preserves real sibling ratios", () => {
  const tree=fixture();
  tree.children!.push({id:"missing",name:"missing",meta:{experimentalMetrics:{hktId:3,composite:9999}}});
  expect(experimentalMetricStatus(tree,"alphaError")).toMatchObject({available:2,total:3});
  const [a,b]=areas(tree,"alphaError"); expect(b/a).toBeCloseTo(9,5);
  const weighted=applyExperimentalSizeMetric(tree,"alphaError");
  expect(weighted.children![2].meta?.experimentalMetricProvenance).toBe("unavailable");
  expect(weighted.children![2].value).toBeCloseTo(1/3);
  expect(weighted.children!.reduce((sum,n)=>sum+(n.value??0),0)).toBeCloseTo(1);
});
it("260 final scopes with three decisions change actual D3 geometry", () => {
  const tree=buildTreemapFromSecaVerboseTree({
    hkts:Array.from({length:260},(_,i)=>({hkt_id:i+1,parent_node_id:0})),
    nodes:Array.from({length:260},(_,i)=>({node_id:i+1,hkt_id:i+1,sources:[]})),
    decision_diagnostics:[1,2,3].map(id=>({hkt_id:id,output_hkt_id:id,should_reconstruct:false})),
    display_diagnostics:Array.from({length:245},(_,i)=>({hkt_id:i+1,mapped_source_count:260-i,paper_alpha_error:(i+1)/260}))
  },{activeWindowDays:30});
  expect(experimentalMetricStatus(tree,"alphaError")).toMatchObject({available:245,total:260});
  const layout=(metric:ExperimentalSizeMetric)=>computeLayout(buildWeightedTree(applyExperimentalSizeMetric(tree,metric),new Set(),tuning),2000,2000,tuning);
  const area=(layout:ReturnType<typeof computeLayout>,id:number)=>{const r=layout.byId.get(`node::${id}`)!;return (r.x1-r.x0)*(r.y1-r.y0);};
  const mapped=layout("mappedSourceCount"), alpha=layout("alphaError");
  expect(area(mapped,1)).toBeGreaterThan(area(mapped,245));
  expect(area(alpha,1)).toBeLessThan(area(alpha,245));
  expect(tree.children![244].meta!.experimentalMetrics!.triggeredScore).toBeUndefined();
});
it("child leaf budgets conserve each parent budget", () => {
  const tree=fixture(); tree.children![0].children=[{id:"x",name:"x"},{id:"y",name:"y"}];
  const weighted=applyExperimentalSizeMetric(tree,"alphaError");
  const sum=(n:TreemapNode):number=>n.children?.length?n.children.reduce((a,c)=>a+sum(c),0):n.value??0;
  expect(sum(weighted)).toBeCloseTo(1,12);
  expect(sum(weighted.children![0])).toBeCloseTo(0.1,8);
});

it("a missing distant descendant cannot flatten unrelated sibling geometry", () => {
  const tree=fixture();
  tree.children![0].children=[{id:"distant",name:"missing",meta:{experimentalMetrics:{hktId:900,composite:5000}}}];
  const [a,b]=areas(tree,"alphaError"); expect(b/a).toBeCloseTo(9,5);
  const weighted=applyExperimentalSizeMetric(tree,"alphaError");
  expect(weighted.children![0].children![0].meta?.experimentalMetricProvenance).toBe("unavailable");
});
