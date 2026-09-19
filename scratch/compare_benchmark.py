import json
import os

baseline_path = os.path.join("backend", "baseline_benchmark_results.json")
new_path = os.path.join("backend", "test_benchmark_results.json")

if not os.path.exists(baseline_path) or not os.path.exists(new_path):
    print("Benchmark result files not found yet.")
    exit(0)

with open(baseline_path, "r", encoding="utf-8") as f:
    base = json.load(f)

with open(new_path, "r", encoding="utf-8") as f:
    new = json.load(f)

base_imgs = {img["filename"]: img for img in base.get("images", [])}
new_imgs = {img["filename"]: img for img in new.get("images", [])}

print("| Test Image | Baseline Score | New Score | Score Delta | Baseline Latency | New Latency | Latency Delta | Baseline Blocks | New Blocks |")
print("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")

base_scores = []
new_scores = []
base_times = []
new_times = []

for fname in sorted(base_imgs.keys()):
    b = base_imgs[fname]
    n = new_imgs.get(fname, {})
    
    b_score = b.get("compliance_score", 0.0)
    n_score = n.get("compliance_score", 0.0)
    score_diff = round(n_score - b_score, 1)
    diff_str = f"+{score_diff}%" if score_diff > 0 else (f"{score_diff}%" if score_diff < 0 else "0.0%")
    
    b_time = b.get("processing_time_sec", 0.0)
    n_time = n.get("processing_time_sec", 0.0)
    time_diff = round(n_time - b_time, 2)
    time_str = f"+{time_diff}s" if time_diff > 0 else f"{time_diff}s"
    
    b_blocks = b.get("total_detected_blocks", 0)
    n_blocks = n.get("total_detected_blocks", 0)
    
    base_scores.append(b_score)
    new_scores.append(n_score)
    base_times.append(b_time)
    new_times.append(n_time)
    
    print(f"| `{fname}` | {b_score:.1f}% | {n_score:.1f}% | **{diff_str}** | {b_time:.2f}s | {n_time:.2f}s | {time_str} | {b_blocks} | {n_blocks} |")

avg_b_score = sum(base_scores) / len(base_scores) if base_scores else 0
avg_n_score = sum(new_scores) / len(new_scores) if new_scores else 0
total_b_time = sum(base_times)
total_n_time = sum(new_times)

print(f"\n**Baseline Average Score:** {avg_b_score:.2f}%")
print(f"**New Average Score:** {avg_n_score:.2f}% (+{avg_n_score - avg_b_score:.2f}%)")
print(f"**Total Benchmark Latency:** Baseline = {total_b_time:.2f}s | New = {total_n_time:.2f}s")
