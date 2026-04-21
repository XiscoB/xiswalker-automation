"""Visual template matching and screenshot utilities."""

import time
from typing import Tuple, Optional, List
from pathlib import Path

try:
    import cv2
    import numpy as np
    from PIL import ImageGrab
except ImportError:
    pass  # Handled graceful failure when not installed


class TemplateMatchResult:
    """Result of a template matching operation."""
    
    def __init__(self, found: bool, x: int = 0, y: int = 0, 
                 confidence: float = 0.0, template_w: int = 0, template_h: int = 0):
        self.found = found
        self.x = x  # Top-left X of match
        self.y = y  # Top-left Y of match
        self.center_x = x + template_w // 2 if found else 0
        self.center_y = y + template_h // 2 if found else 0
        self.confidence = confidence
        self.template_w = template_w
        self.template_h = template_h
    
    def get_relative(self, offset_x: int, offset_y: int) -> Tuple[int, int]:
        """Get coordinates relative to the template's top-left corner.
        
        Args:
            offset_x: X offset from template's top-left
            offset_y: Y offset from template's top-left
            
        Returns:
            (absolute_x, absolute_y) screen coordinates
        """
        return (self.x + offset_x, self.y + offset_y)


class VisualMatcher:
    """Matches visual templates in screenshots."""

    def __init__(self, templates_dir: Path):
        self.templates_dir = templates_dir

    def capture_roi(self, roi: Optional[List[int]] = None) -> 'np.ndarray':
        """Capture a screenshot, optionally cropped to an ROI (x, y, w, h)."""
        bbox = None
        if roi and len(roi) == 4:
            x, y, w, h = roi
            bbox = (x, y, x + w, y + h)
        
        # ImageGrab.grab returns PIL Image. Convert to numpy array for cv2
        img = ImageGrab.grab(bbox=bbox, all_screens=True)
        # Convert RGB to BGR for cv2
        img_np = np.array(img)
        if len(img_np.shape) == 3 and img_np.shape[2] == 3: # Check if it's RGB
            img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        elif len(img_np.shape) == 3 and img_np.shape[2] == 4: # RGBA
            img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGBA2BGR)
        else:
            img_cv = img_np
        return img_cv
        
    def match_template(self, image: 'np.ndarray', template: 'np.ndarray', threshold: float) -> Tuple[bool, Tuple[int, int], float]:
        """Pure matching function.
        
        Args:
            image: screen numpy array (BGR).
            template: template numpy array (BGR).
            threshold: matching threshold 0.0-1.0.
            
        Returns:
            (found, (center_x, center_y), max_val)
        """
        # Template matching requires template to be <= image size
        if template.shape[0] > image.shape[0] or template.shape[1] > image.shape[1]:
            return False, (0, 0), 0.0
            
        res = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        
        if max_val >= threshold:
            # calculate center
            h, w = template.shape[:2]
            center_x = max_loc[0] + w // 2
            center_y = max_loc[1] + h // 2
            return True, (center_x, center_y), max_val
            
        return False, (0, 0), max_val

    def find_and_click(self, template_name: str, roi: Optional[List[int]] = None, threshold: float = 0.8) -> Tuple[bool, Tuple[int, int]]:
        """Find a template on screen and return its center coordinates.
        
        Args:
            template_name: Name of the template file in templates_dir.
            roi: Region of interest [x, y, w, h].
            threshold: Confidence threshold (0.0 to 1.0).
            
        Returns:
            (found, (absolute_x, absolute_y))
        """
        template_path = self.templates_dir / template_name
        if not template_path.exists():
            print(f"⚠️ Template missing: {template_path}")
            return False, (0, 0)
            
        template_img = cv2.imread(str(template_path))
        if template_img is None:
            print(f"⚠️ Failed to load template: {template_path}")
            return False, (0, 0)
            
        screen_img = self.capture_roi(roi)
        
        found, (cx, cy), conf = self.match_template(screen_img, template_img, threshold)
        if found:
            # If ROI was provided, offset the relative center back to absolute screen coords
            abs_x, abs_y = cx, cy
            if roi and len(roi) == 4:
                abs_x += roi[0]
                abs_y += roi[1]
            return True, (abs_x, abs_y)
            
        return False, (0, 0)

    def find_template(self, template_name: str, roi: Optional[List[int]] = None, 
                      threshold: float = 0.8) -> TemplateMatchResult:
        """Find a template on screen and return detailed match result.
        
        Args:
            template_name: Name of the template file in templates_dir.
            roi: Region of interest [x, y, w, h]. If None, searches full screen.
            threshold: Confidence threshold (0.0 to 1.0).
            
        Returns:
            TemplateMatchResult with found flag, coordinates, and confidence.
        """
        template_path = self.templates_dir / template_name
        if not template_path.exists():
            print(f"⚠️ Template missing: {template_path}")
            return TemplateMatchResult(False)
            
        template_img = cv2.imread(str(template_path))
        if template_img is None:
            print(f"⚠️ Failed to load template: {template_path}")
            return TemplateMatchResult(False)
        
        template_h, template_w = template_img.shape[:2]
        screen_img = self.capture_roi(roi)
        
        found, (cx, cy), conf = self.match_template(screen_img, template_img, threshold)
        
        if found:
            # Calculate top-left from center
            top_left_x = cx - template_w // 2
            top_left_y = cy - template_h // 2
            
            # If ROI was provided, offset back to absolute screen coords
            if roi and len(roi) == 4:
                top_left_x += roi[0]
                top_left_y += roi[1]
                cx += roi[0]
                cy += roi[1]
                
            return TemplateMatchResult(
                found=True, 
                x=top_left_x, 
                y=top_left_y,
                confidence=conf,
                template_w=template_w,
                template_h=template_h
            )
            
        return TemplateMatchResult(False, confidence=conf)

    def find_template_with_retry(self, template_name: str, 
                                  max_attempts: int = 3,
                                  delay_between: float = 1.0,
                                  roi: Optional[List[int]] = None, 
                                  threshold: float = 0.8) -> TemplateMatchResult:
        """Find a template with multiple retry attempts.
        
        Args:
            template_name: Name of the template file.
            max_attempts: Maximum number of search attempts (default: 3).
            delay_between: Delay in seconds between attempts (default: 1.0).
            roi: Region of interest [x, y, w, h]. If None, searches full screen.
            threshold: Confidence threshold (0.0 to 1.0).
            
        Returns:
            TemplateMatchResult. found=True if template was found, False otherwise.
        """
        for attempt in range(max_attempts):
            result = self.find_template(template_name, roi, threshold)
            
            if result.found:
                return result
                
            if attempt < max_attempts - 1:
                time.sleep(delay_between)
                
        return TemplateMatchResult(False)

    def get_screen_size(self) -> Tuple[int, int]:
        """Get the primary screen size.
        
        Returns:
            (width, height) of the screen
        """
        img = ImageGrab.grab()
        return img.size
