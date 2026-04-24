"""
Thumbnail Generator for Xity Sleep Bible — v1.0
===============================================
Features:
    1. Extracts high-quality frame from background video.
    2. Applies Cyber-Gold aesthetic overlays (Logo, Title, Sleep Angle).
    3. Uses Pillow for professional typography and branding.
"""

import logging
import os
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import cv2
import numpy as np

from src.utils.logger import get_logger

logger = get_logger("video.thumbnail")

# Brand Assets
LOGO_PATH = Path("assets/brand/logo_gold.png")
FONT_BOLD = "assets/fonts/Montserrat-Bold.ttf"
FONT_REG  = "assets/fonts/Montserrat-Medium.ttf"

# Aesthetics
GOLD_COLOR = (197, 160, 40)  # #C5A028
NAVY_COLOR = (26, 42, 74)    # #1A2A4A

def generate_thumbnail(
    visual_path: str,
    title: str,
    sleep_angle: str,
    output_path: str,
) -> str:
    """
    Generate a premium YouTube thumbnail.
    """
    logger.info(f"[thumbnail] Generating for: {title}")
    
    # 1. Extract base frame from video
    cap = cv2.VideoCapture(str(visual_path))
    cap.set(cv2.CAP_PROP_POS_FRAMES, 30) # get frame at 1s
    success, frame = cap.read()
    cap.release()
    
    if not success:
        # Fallback to solid navy if video fail
        img = Image.new("RGB", (1280, 720), color=NAVY_COLOR)
    else:
        # Convert BGR to RGB
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame)
        img = img.resize((1280, 720), Image.Resampling.LANCZOS)
    
    # 2. Apply "Atmospheric Blur" and darkening for readability
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 100)) # Darken 40%
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    
    draw = ImageDraw.Draw(img)
    
    # 3. Add Brand Logo (Top Left)
    if LOGO_PATH.exists():
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            logo.thumbnail((180, 180))
            img.paste(logo, (40, 40), logo)
        except: pass
    
    # 4. Add "Sleep Bible" watermark (Bottom Right)
    try:
        font_watermark = ImageFont.truetype(FONT_REG, 24)
        draw.text((1100, 660), "Xity Sleep Bible", font=font_watermark, fill=(255, 255, 255, 150))
    except: pass

    # 5. Add Main Title (Center Left, Gold)
    # Wrap text if too long
    try:
        title_font = ImageFont.truetype(FONT_BOLD, 72)
        
        # Simple text wrapping for 1280px width
        words = title.split()
        lines = []
        current_line = []
        for word in words:
            current_line.append(word)
            w, h = draw.textbbox((0, 0), " ".join(current_line), font=title_font)[2:]
            if w > 800:
                current_line.pop()
                lines.append(" ".join(current_line))
                current_line = [word]
        lines.append(" ".join(current_line))
        
        y_text = 240
        for line in lines:
            # Draw shadow
            draw.text((64, y_text + 4), line, font=title_font, fill=(0, 0, 0, 200))
            # Draw Gold text
            draw.text((60, y_text), line, font=title_font, fill=GOLD_COLOR)
            y_text += 90
            
        # 6. Add Sleep Angle (Subtitle, White)
        sub_font = ImageFont.truetype(FONT_REG, 42)
        draw.text((64, y_text + 24), sleep_angle, font=sub_font, fill=(0, 0, 0, 200))
        draw.text((60, y_text + 20), sleep_angle, font=sub_font, fill=(255, 255, 255))
        
    except Exception as e:
        logger.warning(f"[thumbnail] Font rendering failed: {e}")
        # Fallback simple text
        draw.text((60, 300), title, fill=GOLD_COLOR)

    # Save final
    img.convert("RGB").save(output_path, "JPEG", quality=95)
    logger.info(f"[thumbnail] Saved: {output_path}")
    return str(output_path)
