"""Download public OCR weights before the event demo; never accepts documents."""
import argparse
import json
import os
import shutil
from pathlib import Path
from unittest.mock import patch


def check_models(root):
    root = Path(root)
    names = ('PP-OCRv5_mobile_det', 'PP-OCRv5_mobile_rec')
    return {name: (root / name / 'inference.yml').is_file() and
                  (root / name / 'inference.pdiparams').is_file() for name in names}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models-dir', type=Path, required=True)
    parser.add_argument('--download', action='store_true', help='Download public weights, no input documents')
    args = parser.parse_args()
    root = args.models_dir.resolve()
    if any('onedrive' in p.lower() for p in root.parts) or root.is_relative_to(Path(__file__).resolve().parents[1]):
        parser.error('Store weights in a local folder outside the repository and OneDrive.')
    if args.download and not all(check_models(root).values()):
        root.mkdir(parents=True, exist_ok=True)
        cache = root / 'download-cache'
        os.environ['PADDLE_PDX_CACHE_HOME'] = str(cache)
        os.environ['MODELSCOPE_CACHE'] = str(cache / 'modelscope')
        os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
        os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
        import torch  # noqa: F401
        original = os.path.expanduser
        def expand(path):
            path = os.fspath(path)
            if path == '~': return str(cache)
            if path.startswith(('~/', '~\\')): return str(cache / path[2:])
            return original(path)
        with patch('os.path.expanduser', side_effect=expand):
            import paddle  # noqa: F401
        from paddleocr import PaddleOCR
        PaddleOCR(device='cpu', enable_mkldnn=False, cpu_threads=2,
                  text_detection_model_name='PP-OCRv5_mobile_det',
                  text_recognition_model_name='PP-OCRv5_mobile_rec',
                  use_doc_orientation_classify=False, use_doc_unwarping=False,
                  use_textline_orientation=False)
        for name in check_models(root):
            shutil.copytree(cache / 'official_models' / name, root / name, dirs_exist_ok=True)
    status = check_models(root)
    print(json.dumps({'models': status, 'ready_for_local_inference': all(status.values())}))
    if not all(status.values()): raise SystemExit(2)


if __name__ == '__main__':
    main()
