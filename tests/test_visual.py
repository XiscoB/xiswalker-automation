"""Tests for pure logic in visual matching."""

import numpy as np
from pathlib import Path

def test_visual_matcher_logic():
    from xiswalker.visual import VisualMatcher
    matcher = VisualMatcher(Path("dummy"))
    
    # Create a dummy "screen" 100x100 with random noise to avoid flat image correlation issues
    screen = np.random.randint(0, 100, (100, 100, 3), dtype=np.uint8)
    
    # Create template with varied pixel values to avoid zero variance in CCOEFF_NORMED
    template = np.random.randint(50, 200, (10, 10, 3), dtype=np.uint8)
    
    # Place template on screen
    screen[40:50, 40:50] = template
    
    found, center, conf = matcher.match_template(screen, template, 0.8)
    assert found is True
    assert conf >= 0.99
    # The template is at 40,40 to 50,50. Top-left is 40,40. Center is 40+5=45.
    assert center == (45, 45)
    
def test_visual_matcher_not_found():
    from xiswalker.visual import VisualMatcher
    matcher = VisualMatcher(Path("dummy"))
    
    screen = np.random.randint(0, 100, (100, 100, 3), dtype=np.uint8)
    template = np.random.randint(150, 250, (10, 10, 3), dtype=np.uint8)
    
    # Do NOT place template on screen
    
    found, center, conf = matcher.match_template(screen, template, 0.8)
    assert found is False


def test_template_match_result():
    """Test TemplateMatchResult class."""
    from xiswalker.visual import TemplateMatchResult
    
    # Test found result
    result = TemplateMatchResult(
        found=True,
        x=100,
        y=200,
        confidence=0.95,
        template_w=50,
        template_h=30
    )
    assert result.found is True
    assert result.x == 100
    assert result.y == 200
    assert result.center_x == 125  # 100 + 50//2
    assert result.center_y == 215  # 200 + 30//2
    assert result.confidence == 0.95
    
    # Test relative coordinates
    rel_x, rel_y = result.get_relative(10, 20)
    assert rel_x == 110  # 100 + 10
    assert rel_y == 220  # 200 + 20
    
    # Test not found result
    not_found = TemplateMatchResult(found=False)
    assert not_found.found is False
    assert not_found.x == 0
    assert not_found.y == 0


def test_template_match_result_relative():
    """Test relative coordinate calculations."""
    from xiswalker.visual import TemplateMatchResult
    
    result = TemplateMatchResult(
        found=True,
        x=500,
        y=300,
        confidence=0.9,
        template_w=200,
        template_h=150
    )
    
    # Test various offsets
    assert result.get_relative(0, 0) == (500, 300)  # Top-left
    assert result.get_relative(100, 75) == (600, 375)  # Center
    assert result.get_relative(200, 150) == (700, 450)  # Bottom-right
    assert result.get_relative(-10, -10) == (490, 290)  # Negative offset
