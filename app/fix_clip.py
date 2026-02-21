"""step4_video.py의 CLIPLoader를 LTXAVTextEncoderLoader로 교체"""

with open('app/pipeline/step4_video.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''        "92:60": {
            "inputs": {
                "clip_name": "gemma_3_12B_it_fp4_mixed.safetensors",
                "type": "ltxv"
            },
            "class_type": "CLIPLoader"
        },'''

new = '''        "92:60": {
            "inputs": {
                "text_encoder": "gemma_3_12B_it_fp4_mixed.safetensors",
                "ckpt_name": "ltx-2-19b-dev-fp8.safetensors",
                "device": "default"
            },
            "class_type": "LTXAVTextEncoderLoader"
        },'''

if old in content:
    content = content.replace(old, new)
    with open('app/pipeline/step4_video.py', 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    print("Done! 교체 완료")
else:
    print("매칭 실패")
