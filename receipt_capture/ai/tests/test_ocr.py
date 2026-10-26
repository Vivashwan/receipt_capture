"""OCR tests on generated receipt images. Requires Tesseract (installed in the Docker image)."""

import unittest

import cv2
import numpy as np

from receipt_capture.ai import ocr

LINES = [
	"ANNAPURNA STORES",
	"BILL NO B-1042",
	"DATE 12/03/2026",
	"RICE 5KG    320.00",
	"DAL         160.00",
	"GST          24.00",
	"TOTAL       504.00",
]


def make_receipt(angle: float = 0.0, width: int = 600, noise: bool = False) -> bytes:
	"""Draws a receipt like a small phone photo: dark text on a light, optionally noisy, rotated page."""
	scale = width / 600
	height = int(60 * scale * (len(LINES) + 1))
	image = np.full((height, width, 3), 235, dtype=np.uint8)
	for i, line in enumerate(LINES):
		cv2.putText(
			image,
			line,
			(int(20 * scale), int((i + 1) * 55 * scale)),
			cv2.FONT_HERSHEY_SIMPLEX,
			0.9 * scale,
			(30, 30, 30),
			max(1, int(2 * scale)),
			cv2.LINE_AA,
		)
	if noise:
		rng = np.random.default_rng(42)
		image = np.clip(image.astype(np.int16) + rng.normal(0, 18, image.shape), 0, 255).astype(np.uint8)
	if angle:
		matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
		image = cv2.warpAffine(image, matrix, (width, height), borderValue=(235, 235, 235))
	ok, encoded = cv2.imencode(".png", image)
	assert ok
	return encoded.tobytes()


class TestPreprocess(unittest.TestCase):
	def test_upscales_small_images_and_binarises(self):
		processed = ocr.preprocess(ocr.decode_image(make_receipt(width=400)))

		self.assertGreaterEqual(processed.shape[1], ocr.MIN_WIDTH)
		self.assertEqual(set(np.unique(processed)) - {0, 255}, set())

	def test_estimates_and_corrects_skew(self):
		tilted = ocr.preprocess(ocr.decode_image(make_receipt(angle=6)))
		straight = ocr.preprocess(ocr.decode_image(make_receipt(angle=0)))

		self.assertLess(abs(ocr.estimate_skew(tilted)), 1.5, "deskew should leave the text nearly level")
		self.assertLess(abs(ocr.estimate_skew(straight)), 1.0)

	def test_rejects_non_images(self):
		with self.assertRaises(ocr.OCRError):
			ocr.decode_image(b"%PDF-1.7 not an image")

	def test_blank_image_has_no_text(self):
		blank = cv2.imencode(".png", np.full((400, 600, 3), 255, dtype=np.uint8))[1].tobytes()
		with self.assertRaises(ocr.OCRError):
			ocr.extract_text(blank)


class TestExtractText(unittest.TestCase):
	def assert_reads_receipt(self, text: str):
		upper = text.upper()
		self.assertIn("ANNAPURNA", upper)
		self.assertIn("TOTAL", upper)
		self.assertIn("504", upper)

	def test_reads_clean_receipt(self):
		self.assert_reads_receipt(ocr.extract_text(make_receipt()))

	def test_reads_tilted_noisy_phone_photo(self):
		self.assert_reads_receipt(ocr.extract_text(make_receipt(angle=5, width=450, noise=True)))
