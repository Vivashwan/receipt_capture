"""Receipt image preprocessing (OpenCV) and text recognition (Tesseract).

Phone photos of receipts are small, tilted, unevenly lit and noisy, all of which
hurt OCR. Each step below fixes one of those before Tesseract reads the text.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytesseract

# Tesseract is most accurate when capital letters are roughly 20-30 px tall
MIN_WIDTH = 1000
MAX_SKEW_DEGREES = 15


class OCRError(RuntimeError):
	"""The image could not be decoded or contained no readable text."""


def decode_image(image_bytes: bytes) -> np.ndarray:
	image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
	if image is None:
		raise OCRError("File is not a readable image (supported: JPEG, PNG, WebP, BMP, TIFF)")
	return image


def preprocess(image: np.ndarray) -> np.ndarray:
	"""Returns a clean, upright, black-on-white version of the receipt."""
	gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image

	# 1. Upscale small photos so characters are large enough to recognise
	if gray.shape[1] < MIN_WIDTH:
		scale = MIN_WIDTH / gray.shape[1]
		gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

	# 2. Remove sensor noise while keeping character edges sharp
	gray = cv2.bilateralFilter(gray, d=7, sigmaColor=50, sigmaSpace=50)

	# 3. Adaptive threshold copes with shadows and uneven lighting across the page
	binary = cv2.adaptiveThreshold(
		gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, blockSize=31, C=15
	)

	# 4. Straighten a tilted photo
	return deskew(binary)


def estimate_skew(binary: np.ndarray) -> float:
	"""Angle (degrees) of the text block, from the minimum-area rectangle around ink pixels."""
	ink = np.column_stack(np.where(binary < 128))
	if len(ink) < 50:
		return 0.0
	angle = cv2.minAreaRect(ink[:, ::-1].astype(np.float32))[-1]
	# OpenCV's angle convention changed across versions ((0, 90] vs [-90, 0)), and a
	# rectangle's angle is ambiguous by 90 degrees; map it to the smallest rotation.
	if angle > 45:
		angle -= 90
	elif angle <= -45:
		angle += 90
	return float(angle)


def deskew(binary: np.ndarray) -> np.ndarray:
	angle = estimate_skew(binary)
	# Ignore tiny tilts (noise) and implausible ones (probably not a text block)
	if abs(angle) < 0.5 or abs(angle) > MAX_SKEW_DEGREES:
		return binary
	height, width = binary.shape[:2]
	matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
	return cv2.warpAffine(
		binary,
		matrix,
		(width, height),
		flags=cv2.INTER_CUBIC,
		borderMode=cv2.BORDER_CONSTANT,
		borderValue=255,
	)


def extract_text(image_bytes: bytes, lang: str = "eng") -> str:
	"""Full pipeline: decode -> preprocess -> Tesseract. Raises OCRError if nothing is readable."""
	processed = preprocess(decode_image(image_bytes))
	# --psm 4: a single column of text of variable sizes, the typical receipt layout
	text = pytesseract.image_to_string(processed, lang=lang, config="--oem 1 --psm 4")
	text = "\n".join(line.rstrip() for line in text.splitlines() if line.strip())
	if len(text) < 10:
		raise OCRError("No readable text found on the image; try a sharper, well-lit photo")
	return text
