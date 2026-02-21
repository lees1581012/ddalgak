"""ComfyUI history에서 최근 작업 출력 구조 확인"""
import json
import urllib.request

# 최근 history 가져오기
resp = urllib.request.urlopen("http://localhost:8000/history?max_items=1")
history = json.loads(resp.read())

for prompt_id, data in history.items():
    print(f"prompt_id: {prompt_id}")
    print(f"status: {data.get('status', {})}")
    outputs = data.get('outputs', {})
    print(f"output 노드 수: {len(outputs)}")
    for node_id, node_out in outputs.items():
        print(f"\n  노드 {node_id}:")
        for key, val in node_out.items():
            print(f"    {key}: {val}")