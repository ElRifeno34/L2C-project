"""Run one local ML backend on prepared crops. Outputs may be confidential."""
import argparse
import json
import os
import re
import time
from pathlib import Path


def tokens(value):
    # Canadian bar designations: do not mistake lengths ending in MM for bars.
    return set(re.findall(r"(?<![\dA-Z])(?:10|15|20|25|30|35|45|55)M(?![\dA-Z])",
                          value.upper()))


def quantity_pairs(value):
    return set(re.findall(
        r"(?<!\d)(\d{1,3})\s*[-–]\s*((?:10|15|20|25|30|35|45|55)M)(?![A-Z\d])",
        value.upper()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["paddle", "florence"], required=True)
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path,
                        help="Downloaded Florence model directory; enables offline loading.")
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        parser.error("Save results outside the repository and cloud-synced folders.")
    samples = json.loads(args.samples.read_text(encoding="utf-8"))
    started = time.perf_counter()
    if args.backend == "paddle":
        # Load PyTorch DLLs before Paddle: ModelScope imports torch transitively.
        import torch
        # Paddle's dataset module creates a cache at import time and has no
        # dedicated override. Redirect its import-time home lookup locally,
        # without changing the user's HOME/USERPROFILE environment.
        from unittest.mock import patch
        runtime_home = args.output.resolve().parent / "paddle-runtime"
        runtime_home.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("MODELSCOPE_CACHE", str(runtime_home / "modelscope"))
        original_expanduser = os.path.expanduser
        def local_expanduser(path):
            path = os.fspath(path)
            if path == "~":
                return str(runtime_home)
            if path.startswith(("~/", "~\\")):
                return str(runtime_home / path[2:])
            return original_expanduser(path)
        with patch("os.path.expanduser", side_effect=local_expanduser):
            import paddle
        from paddleocr import PaddleOCR
        model = PaddleOCR(device="cpu", enable_mkldnn=False, cpu_threads=2,
                          text_detection_model_name="PP-OCRv5_mobile_det",
                          text_recognition_model_name="PP-OCRv5_mobile_rec",
                          use_doc_orientation_classify=False, use_doc_unwarping=False,
                          use_textline_orientation=False)
    else:
        import torch
        from transformers import AutoModelForCausalLM, AutoProcessor
        model_id = str(args.model_dir.resolve()) if args.model_dir else "microsoft/Florence-2-base"
        model = AutoModelForCausalLM.from_pretrained(
            model_id, trust_remote_code=True, torch_dtype=torch.float32,
            attn_implementation="eager", low_cpu_mem_usage=True,
            use_safetensors=True, local_files_only=bool(args.model_dir)).eval()
        processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
        torch.set_num_threads(2)
    load_seconds = time.perf_counter() - started
    results = []
    for index, sample in enumerate(samples):
        tick = time.perf_counter()
        ocr_annotations = []
        if args.backend == "paddle":
            predictions = list(model.predict(sample["file"]))
            data = predictions[0].json
            if isinstance(data, str):
                data = json.loads(data)
            payload = data.get("res", data)
            text = " ".join(payload.get("rec_texts", []))
            for label, polygon, score in zip(payload.get("rec_texts", []),
                                             payload.get("rec_polys", []),
                                             payload.get("rec_scores", [])):
                entry = {"text": label, "polygon_crop_pixels": polygon,
                         "recognition_score": float(score)}
                if "render_scale" in sample and "crop_origin_pixels" in sample:
                    scale = sample["render_scale"]
                    ox, oy = sample["crop_origin_pixels"]
                    points = [[(p[0]+ox)/scale, (p[1]+oy)/scale] for p in polygon]
                    entry["bbox_pdf_points"] = [min(p[0] for p in points), min(p[1] for p in points),
                                                max(p[0] for p in points), max(p[1] for p in points)]
                    box = entry["bbox_pdf_points"]
                    entry["centre_pdf_points"] = [(box[0]+box[2])/2, (box[1]+box[3])/2]
                else:
                    entry["coordinate_status"] = "rerun prepare_samples to obtain the crop transform"
                ocr_annotations.append(entry)
        else:
            from PIL import Image
            image = Image.open(sample["file"]).convert("RGB")
            inputs = processor(text="<OCR>", images=image, return_tensors="pt")
            with torch.inference_mode():
                output = model.generate(**inputs, max_new_tokens=256,
                                        num_beams=1, do_sample=False)
            text = processor.batch_decode(output, skip_special_tokens=False)[0]
            data = processor.post_process_generation(
                text, task="<OCR>", image_size=image.size)
            text = str(data.get("<OCR>", ""))
        predicted = tokens(text)
        reference = tokens(" ".join(sample["native_text"]))
        reference_pairs = quantity_pairs(" ".join(sample["native_text"]))
        predicted_pairs = quantity_pairs(text)
        result = {"sample": index + 1, "seconds": round(time.perf_counter()-tick, 3),
                  "text": text, "native_bar_tokens": sorted(reference),
                  "predicted_bar_tokens": sorted(predicted),
                  "matching_bar_tokens": len(predicted & reference),
                  "reference_bar_tokens": len(reference),
                  "predicted_bar_token_count": len(predicted),
                  "matching_quantity_pairs": len(predicted_pairs & reference_pairs),
                  "reference_quantity_pairs": len(reference_pairs),
                  "predicted_quantity_pairs": len(predicted_pairs)}
        result["ocr_annotations"] = ocr_annotations
        results.append(result)
        print(json.dumps({k: v for k, v in result.items()
                          if k not in ("text", "native_bar_tokens", "predicted_bar_tokens", "ocr_annotations")}), flush=True)
    report = {"backend": args.backend, "load_seconds": round(load_seconds, 3),
              "results": results,
              "metric_note": "Agreement with native PDF text, not manually verified accuracy."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"backend": args.backend, "load_seconds": report["load_seconds"]}))


if __name__ == "__main__":
    main()
