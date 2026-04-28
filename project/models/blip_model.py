from __future__ import annotations

from pathlib import Path

import torch
from PIL import Image
from transformers import BlipForConditionalGeneration, BlipProcessor
from transformers.utils import logging as transformers_logging


transformers_logging.set_verbosity_error()


class BlipCaptioner:
    def __init__(
        self,
        model_name: str = "Salesforce/blip-image-captioning-base",
        device: str | None = None,
    ) -> None:
        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.processor: BlipProcessor | None = None
        self.model: BlipForConditionalGeneration | None = None

    def _ensure_loaded(self) -> None:
        if self.processor is not None and self.model is not None:
            return

        self.processor = BlipProcessor.from_pretrained(self.model_name, use_fast=False)
        self.model = BlipForConditionalGeneration.from_pretrained(self.model_name).to(self.device)
        self.model.eval()

    def caption_image(self, image_path: Path, max_new_tokens: int = 40) -> str:
        self._ensure_loaded()
        assert self.processor is not None and self.model is not None

        with Image.open(image_path) as image:
            image = image.convert("RGB")
            inputs = self.processor(images=image, return_tensors="pt").to(self.device)

        with torch.no_grad():
            output = self.model.generate(**inputs, max_new_tokens=max_new_tokens)

        return self.processor.decode(output[0], skip_special_tokens=True).strip()

    def caption_pil_image(self, image: Image.Image, max_new_tokens: int = 40) -> str:
        self._ensure_loaded()
        assert self.processor is not None and self.model is not None

        rgb = image.convert("RGB")
        inputs = self.processor(images=rgb, return_tensors="pt").to(self.device)

        with torch.no_grad():
            output = self.model.generate(**inputs, max_new_tokens=max_new_tokens)

        return self.processor.decode(output[0], skip_special_tokens=True).strip()
