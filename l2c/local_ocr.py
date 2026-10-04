"""CPU OCR with explicitly preloaded local weights; no remote inference."""
import os
from pathlib import Path
from unittest.mock import patch


class LocalPaddle:
    def __init__(self, models_dir, runtime_dir):
        root = Path(models_dir).resolve()
        names = ('PP-OCRv5_mobile_det', 'PP-OCRv5_mobile_rec')
        paths = [root / name for name in names]
        if not all((p / 'inference.yml').is_file() for p in paths):
            raise ValueError('Preload both PP-OCRv5_mobile models before running offline inference.')
        runtime = Path(runtime_dir).resolve()
        runtime.mkdir(parents=True, exist_ok=True)
        os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
        os.environ['PADDLE_PDX_CACHE_HOME'] = str(runtime / 'paddle-cache')
        os.environ['MODELSCOPE_CACHE'] = str(runtime / 'modelscope')
        os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
        os.environ['HF_HUB_OFFLINE'] = '1'
        # Windows: import Torch DLLs before Paddle's transitive imports.
        import torch  # noqa: F401
        original = os.path.expanduser
        def expand(path):
            path = os.fspath(path)
            if path == '~':
                return str(runtime)
            if path.startswith(('~/', '~\\')):
                return str(runtime / path[2:])
            return original(path)
        with patch('os.path.expanduser', side_effect=expand):
            import paddle  # noqa: F401
        from paddleocr import PaddleOCR
        self.model = PaddleOCR(
            device='cpu', enable_mkldnn=False, cpu_threads=2,
            text_detection_model_name=names[0], text_detection_model_dir=str(paths[0]),
            text_recognition_model_name=names[1], text_recognition_model_dir=str(paths[1]),
            use_doc_orientation_classify=False, use_doc_unwarping=False,
            use_textline_orientation=False)

    def words(self, image, origin=(0, 0), scale=2):
        import json
        import numpy as np
        data = list(self.model.predict(np.asarray(image.convert('RGB'))))[0].json
        if isinstance(data, str):
            data = json.loads(data)
        data = data.get('res', data)
        words = []
        for text, polygon, score in zip(data.get('rec_texts', []),
                                        data.get('rec_polys', []), data.get('rec_scores', [])):
            if float(score) < .5:
                continue
            xs = [p[0] / scale + origin[0] for p in polygon]
            ys = [p[1] / scale + origin[1] for p in polygon]
            words.append({'text': text, 'x0': min(xs), 'x1': max(xs),
                          'top': min(ys), 'bottom': max(ys), 'ocr_score': float(score)})
        return words
