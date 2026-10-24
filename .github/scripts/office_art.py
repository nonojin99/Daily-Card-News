#!/usr/bin/env python3
"""사무실 화면(office/) 그림 시안을 Gemini 로 만든다 — office/art/requests.json 의 항목마다 office/art/out/<id>.jpg.

이미 있는 id 는 건너뛴다(다시 만들려면 id 를 바꾼다, 예: hero-hq-a2). 실패한 항목은 로그만 남기고 다음으로 간다.
API 호출은 카드 일러스트와 같은 함수(make_images.call)를 쓴다. 비용은 장당 약 0.04달러.
"""
import io, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import make_images as mi  # noqa: E402

REQ, OUT = "office/art/requests.json", "office/art/out"


def main():
    if not mi.KEY:
        print("office art: GEMINI_API_KEY not set — skip"); return
    model = os.environ.get("OFFICE_IMAGE_MODEL", "").strip()
    if model: mi.MODEL = model
    spec = json.load(open(REQ, encoding="utf-8"))
    common = spec.get("common", "")
    made = 0
    for it in spec["items"]:
        path = f"{OUT}/{it['id']}.jpg"
        if os.path.exists(path): continue
        prompt = it["prompt"].strip() + " " + common
        try:
            raw = mi.call(prompt)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::office art {it['id']} failed: {e}"); continue
        from PIL import Image
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        if im.width > 1920: im = im.resize((1920, round(im.height * 1920 / im.width)), Image.LANCZOS)
        os.makedirs(OUT, exist_ok=True)
        im.save(path, "JPEG", quality=88, optimize=True, progressive=True)
        made += 1
        print(f"office art: {path} ({im.width}x{im.height}, model {mi.MODEL})")
    print(f"office art: made {made}")


if __name__ == "__main__":
    main()
