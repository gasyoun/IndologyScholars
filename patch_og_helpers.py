import re

patch_content = '''
import os
import textwrap
import urllib.request
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None

def get_roboto_font():
    font_path = "assets/Roboto-Bold.ttf"
    if not os.path.exists(font_path):
        os.makedirs("assets", exist_ok=True)
        url = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Bold.ttf"
        urllib.request.urlretrieve(url, font_path)
    return font_path

def create_dynamic_og_image(lines, filepath):
    if Image is None:
        return # Fallback if Pillow fails
    if os.path.exists(filepath):
        return
        
    width, height = 1200, 630
    bg_color = (15, 23, 42) # #0f172a
    text_color = (255, 255, 255)
    accent_color = (136, 192, 208)
    
    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)
    font_path = get_roboto_font()
    
    try:
        font_large = ImageFont.truetype(font_path, 80)
        font_small = ImageFont.truetype(font_path, 48)
        font_tiny = ImageFont.truetype(font_path, 36)
    except Exception:
        font_large = font_small = font_tiny = ImageFont.load_default()
        
    y = 120
    margin = 80
    
    main_text = lines[0]
    wrapped_main = textwrap.wrap(main_text, width=28)
    if len(wrapped_main) > 3:
        wrapped_main = wrapped_main[:2] + [wrapped_main[2] + "..."]
        
    for line in wrapped_main:
        draw.text((margin, y), line, font=font_large, fill=text_color)
        y += 100
        
    y += 40
    for line in lines[1:]:
        draw.text((margin, y), line, font=font_small, fill=accent_color)
        y += 70
        
    draw.text((margin, height - 80), "Российский индологический научный архив", font=font_tiny, fill=(100, 116, 139))
    
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    img.save(filepath)

'''

with open("publication_helpers.py", "r", encoding="utf-8") as f:
    content = f.read()

# Inject functions before def trim_description
if "def create_dynamic_og_image" not in content:
    content = content.replace("def trim_description(", patch_content + "\n\ndef trim_description(")
    
# Update page_shell signature and logic
old_shell = 'def page_shell(title, description, canonical_path, body, structured_data=None, extra_head="", robots="index, follow", language="ru"):'
new_shell = 'def page_shell(title, description, canonical_path, body, structured_data=None, extra_head="", robots="index, follow", language="ru", custom_og_image=None):'
content = content.replace(old_shell, new_shell)

if "og_image_url=OG_IMAGE_URL," in content:
    content = content.replace(
        "og_image_url=OG_IMAGE_URL,",
        'og_image_url=site_url(custom_og_image) if custom_og_image else OG_IMAGE_URL,'
    )

with open("publication_helpers.py", "w", encoding="utf-8") as f:
    f.write(content)

print("publication_helpers.py updated.")
