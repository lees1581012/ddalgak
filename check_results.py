import json
data = json.load(open('output/20260219_225351/video_results.json', encoding='utf-8'))
for r in data:
    sid = r.get('scene_id', '?')
    st = r.get('status', '?')
    err = r.get('error', '')[:200]
    vp = r.get('video_path', '')
    print(f"{sid}: {st} | {err or vp}")
