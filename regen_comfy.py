import json
import time
import urllib.request
import urllib.parse
import os
import sys

PROJECT = os.path.join('output', '20260304_101148')
JSON_PATH = os.path.join(PROJECT, 'image_results.json')
TEMPLATE_PATH = 'comfy_test_workflow.json'
COMFY_BASE = 'http://localhost:8000'

def load_json(p):
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(obj, p):
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def comfy_post_prompt(template_prompt):
    body = json.dumps({'prompt': template_prompt}).encode('utf-8')
    req = urllib.request.Request(f'{COMFY_BASE}/prompt', data=body, headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8'))


def comfy_get_history(pid):
    url = f'{COMFY_BASE}/history/{pid}'
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            txt = r.read().decode('utf-8')
            if not txt or txt.strip() == '{}':
                return None
            return json.loads(txt)
    except Exception:
        return None


def download_view(filename, filetype='output', subfolder=''):
    params = {'filename': filename, 'type': filetype}
    if subfolder:
        params['subfolder'] = subfolder
    url = f"{COMFY_BASE}/view?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read()


if __name__ == '__main__':
    if not os.path.exists(JSON_PATH):
        print('image_results.json not found', file=sys.stderr); sys.exit(1)
    results = load_json(JSON_PATH)
    template = load_json(TEMPLATE_PATH).get('prompt')
    failed_items = [r for r in results if not (isinstance(r.get('status',''), str) and r.get('status','').startswith('success'))]
    total = len(failed_items)
    print(f'Targeting {total} failed scenes')

    ok = 0
    fail = 0
    for idx, item in enumerate(failed_items, start=1):
        scene_id = int(item.get('scene_id'))
        prompt = item.get('prompt','')
        print(f'[{idx}/{total}] Scene {scene_id} - prompt len {len(prompt)}')
        if not prompt or not prompt.strip():
            item['status'] = 'failed: empty prompt'
            fail += 1
            save_json(results, JSON_PATH)
            continue

        wf = json.loads(json.dumps(template))
        try:
            wf['45']['inputs']['text'] = prompt
            wf['9']['inputs']['filename_prefix'] = f"ddalgak_scene_{scene_id:03d}"
        except Exception as e:
            item['status'] = f'failed: template error {e}'
            fail += 1
            save_json(results, JSON_PATH)
            continue

        try:
            resp = comfy_post_prompt(wf)
        except Exception as e:
            item['status'] = f'failed: post error {e}'
            fail += 1
            save_json(results, JSON_PATH)
            continue

        pid = resp.get('prompt_id')
        if not pid:
            item['status'] = f'failed: no prompt_id in resp'
            fail += 1
            save_json(results, JSON_PATH)
            continue

        # poll history
        history = None
        for i in range(180):
            h = comfy_get_history(pid)
            if h and pid in h:
                history = h[pid]
                break
            time.sleep(1)

        if not history:
            item['status'] = 'failed: timeout'
            fail += 1
            save_json(results, JSON_PATH)
            continue

        status_str = history.get('status', {}).get('status_str')
        if status_str != 'success':
            item['status'] = f'failed: {status_str}'
            fail += 1
            save_json(results, JSON_PATH)
            continue

        # find image output
        outputs = history.get('outputs', {})
        img_info = None
        for k,v in outputs.items():
            if isinstance(v, dict) and 'images' in v and v['images']:
                img_info = v['images'][0]
                break

        if not img_info:
            item['status'] = 'failed: no image output'
            fail += 1
            save_json(results, JSON_PATH)
            continue

        filename = img_info.get('filename')
        subfolder = img_info.get('subfolder','')
        ftype = img_info.get('type','output')
        try:
            data = download_view(filename, filetype=ftype, subfolder=subfolder)
        except Exception as e:
            item['status'] = f'failed: download error {e}'
            fail += 1
            save_json(results, JSON_PATH)
            continue

        dst_dir = os.path.join(PROJECT, 'images')
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, f'scene_{scene_id:03d}.png')
        with open(dst, 'wb') as f:
            f.write(data)

        if os.path.exists(dst):
            item['image_path'] = os.path.abspath(dst)
            item['status'] = 'success'
            ok += 1
            print(f'Scene {scene_id} OK -> {os.path.basename(dst)}')
        else:
            item['status'] = 'failed: save error'
            fail += 1

        save_json(results, JSON_PATH)
        time.sleep(0.5)

    print('DONE', {'ok':ok,'fail':fail})
    save_json(results, JSON_PATH)
