"""
Image preprocessing module for OCR quality enhancement.

This module provides various image preprocessing techniques to improve OCR accuracy:
- Deskewing: Corrects rotation/skew in scanned documents
- Denoising: Removes noise while preserving text edges
- Binarization: Converts to black and white for better text recognition
- Contrast enhancement: Improves text visibility
- Sharpening: Enhances text edges
"""

import cv2
import numpy as np
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class ImagePreprocessor:
    """Handles image preprocessing for OCR enhancement."""

    def __init__(self):
        """Initialize the image preprocessor."""
        pass

    def preprocess(
        self,
        image: np.ndarray,
        deskew: bool = True,
        denoise: bool = True,
        binarize: bool = False,
        enhance_contrast: bool = True,
        sharpen: bool = False,
    ) -> np.ndarray:
        """
        Apply preprocessing pipeline to image.

        Args:
            image: Input image (BGR or grayscale)
            deskew: Apply deskewing/rotation correction
            denoise: Apply denoising
            binarize: Apply binarization (Otsu's method)
            enhance_contrast: Apply CLAHE for contrast enhancement
            sharpen: Apply sharpening filter

        Returns:
            Preprocessed image
        """
        processed = image.copy()

        # Convert to grayscale if needed
        if len(processed.shape) == 3:
            gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
        else:
            gray = processed.copy()

        # Apply deskewing first (before other operations)
        if deskew:
            gray = self._deskew(gray)
            logger.debug("Applied deskewing")

        # Apply contrast enhancement
        if enhance_contrast:
            gray = self._enhance_contrast(gray)
            logger.debug("Applied contrast enhancement")

        # Apply denoising
        if denoise:
            gray = self._denoise(gray)
            logger.debug("Applied denoising")

        # Apply binarization
        if binarize:
            gray = self._binarize(gray)
            logger.debug("Applied binarization")

        # Apply sharpening
        if sharpen:
            gray = self._sharpen(gray)
            logger.debug("Applied sharpening")

        return gray

    def _deskew(self, image: np.ndarray) -> np.ndarray:
        """
        Correct skew/rotation in the image using Hough Transform.

        Args:
            image: Grayscale image

        Returns:
            Deskewed image
        """
        # Make a copy to avoid modifying the original
        img = image.copy()

        # Detect edges
        edges = cv2.Canny(img, 50, 150, apertureSize=3)

        # Detect lines using Hough Transform
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=100,
            minLineLength=100,
            maxLineGap=10
        )

        if lines is None or len(lines) == 0:
            logger.debug("No lines detected for deskewing, returning original")
            return img

        # Calculate angles of all lines
        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))

            # Filter out vertical and horizontal lines (focus on text lines)
            if -45 < angle < 45:
                angles.append(angle)

        if len(angles) == 0:
            logger.debug("No valid angles for deskewing, returning original")
            return img

        # Calculate median angle
        median_angle = np.median(angles)

        # Only rotate if angle is significant (> 0.5 degrees)
        if abs(median_angle) < 0.5:
            logger.debug(f"Skew angle too small ({median_angle:.2f}°), skipping rotation")
            return img

        logger.debug(f"Detected skew angle: {median_angle:.2f}°")

        # Rotate image to correct skew
        (h, w) = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, median_angle, 1.0)

        # Calculate new bounding dimensions
        cos = np.abs(M[0, 0])
        sin = np.abs(M[0, 1])
        new_w = int((h * sin) + (w * cos))
        new_h = int((h * cos) + (w * sin))

        # Adjust rotation matrix
        M[0, 2] += (new_w / 2) - center[0]
        M[1, 2] += (new_h / 2) - center[1]

        rotated = cv2.warpAffine(
            img,
            M,
            (new_w, new_h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )

        return rotated

    def _denoise(self, image: np.ndarray) -> np.ndarray:
        """
        Remove noise while preserving text edges.

        Uses Non-local Means Denoising which is effective for document images.

        Args:
            image: Grayscale image

        Returns:
            Denoised image
        """
        # Use fastNlMeansDenoising for grayscale images
        # h: filter strength (higher = more denoising but may blur text)
        # templateWindowSize: should be odd
        # searchWindowSize: should be odd
        denoised = cv2.fastNlMeansDenoising(
            image,
            h=10,
            templateWindowSize=7,
            searchWindowSize=21
        )

        return denoised

    def _binarize(self, image: np.ndarray) -> np.ndarray:
        """
        Convert image to binary (black and white) using adaptive thresholding.

        This is particularly effective for documents with varying lighting.

        Args:
            image: Grayscale image

        Returns:
            Binarized image
        """
        # Try Otsu's method first
        _, otsu = cv2.threshold(
            image,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

        # Also apply adaptive thresholding
        adaptive = cv2.adaptiveThreshold(
            image,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=15,
            C=10
        )

        # Use the one with better contrast (higher standard deviation)
        if np.std(otsu) > np.std(adaptive):
            logger.debug("Using Otsu binarization")
            return otsu
        else:
            logger.debug("Using adaptive binarization")
            return adaptive

    def _enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        """
        Enhance contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization).

        CLAHE is better than regular histogram equalization for documents
        as it works on small regions and prevents over-amplification of noise.

        Args:
            image: Grayscale image

        Returns:
            Contrast-enhanced image
        """
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(image)

        return enhanced

    def _sharpen(self, image: np.ndarray) -> np.ndarray:
        """
        Sharpen the image to enhance text edges.

        Args:
            image: Grayscale image

        Returns:
            Sharpened image
        """
        # Create sharpening kernel
        kernel = np.array([
            [-1, -1, -1],
            [-1,  9, -1],
            [-1, -1, -1]
        ])

        sharpened = cv2.filter2D(image, -1, kernel)

        return sharpened

    def auto_preprocess(self, image: np.ndarray) -> np.ndarray:
        """
        Apply automatic preprocessing with optimal settings for most documents.

        Args:
            image: Input image

        Returns:
            Preprocessed image
        """
        return self.preprocess(
            image,
            deskew=True,
            denoise=True,
            binarize=False,  # Don't binarize by default, PaddleOCR handles grayscale well
            enhance_contrast=True,
            sharpen=False  # Usually not needed after CLAHE
        )

    def preprocess_for_low_quality(self, image: np.ndarray) -> np.ndarray:
        """
        Aggressive preprocessing for low-quality scans/photos.

        Args:
            image: Input image

        Returns:
            Preprocessed image
        """
        return self.preprocess(
            image,
            deskew=True,
            denoise=True,
            binarize=True,  # Binarize for very low quality
            enhance_contrast=True,
            sharpen=True
        )


# Global instance
_preprocessor = None


def get_preprocessor() -> ImagePreprocessor:
    """Get or create the global preprocessor instance."""
    global _preprocessor
    if _preprocessor is None:
        _preprocessor = ImagePreprocessor()
    return _preprocessor


def preprocess_image(
    image: np.ndarray,
    deskew: bool = True,
    denoise: bool = True,
    **kwargs
) -> np.ndarray:
    """
    Convenience function to preprocess an image.

    Args:
        image: Input image
        deskew: Apply deskewing
        denoise: Apply denoising
        **kwargs: Additional preprocessing options

    Returns:
        Preprocessed image
    """
    preprocessor = get_preprocessor()
    return preprocessor.preprocess(image, deskew=deskew, denoise=denoise, **kwargs)
